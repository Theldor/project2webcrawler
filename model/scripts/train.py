import os
import json  # === CHANGED ===
import csv   # === CHANGED ===
from PIL import ImageOps  # === CHANGED ===

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import datasets, transforms
from torchvision.transforms import InterpolationMode  # === CHANGED ===
import timm
from sklearn.metrics import confusion_matrix, classification_report
import numpy as np

DATA_DIR = "../../dataset_model"

BATCH_SIZE = 16
NUM_EPOCHS = 1000000
LEARNING_RATE = 1e-4

MODEL_NAME = "vit_tiny_patch16_224"


# === CHANGED: 不再叫 DESKTOP_DIR，直接明确 reports / checkpoints 放哪 ===
REPORTS_DIR = "../reports"
CHECKPOINT_DIR = "../checkpoints"

BEST_CHECKPOINT_PATH = os.path.join(CHECKPOINT_DIR, "website_classifier_best.pth")
LAST_CHECKPOINT_PATH = os.path.join(CHECKPOINT_DIR, "website_classifier_last.pth")
CLASS_NAMES_PATH = os.path.join(CHECKPOINT_DIR, "class_names.json")
HISTORY_CSV_PATH = os.path.join(REPORTS_DIR, "training_history.csv")

# === CHANGED: 如果想从某个 checkpoint 继续训练，把路径填在这里；否则保持 None ===
RESUME_CHECKPOINT = None
# 例如：
# RESUME_CHECKPOINT = r"C:\Users\celin\Desktop\project2webcrawler\model\checkpoints\epoch_03.pth"

# === CHANGED: 输入尺寸仍然是 224，但不直接硬拉伸 ===
IMAGE_SIZE = 224
# ----------------------------


from PIL import Image
# 如果之前有：
# from torchvision.transforms import InterpolationMode

def resize_with_padding(img, target_size):
    w, h = img.size
    scale = min(target_size / w, target_size / h)
    new_w = int(w * scale)
    new_h = int(h * scale)

    img = img.resize((new_w, new_h), Image.Resampling.BILINEAR)

    new_img = Image.new("RGB", (target_size, target_size), (0, 0, 0))
    paste_x = (target_size - new_w) // 2
    paste_y = (target_size - new_h) // 2
    new_img.paste(img, (paste_x, paste_y))
    return new_img


def save_text_report(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def save_checkpoint(path, model, optimizer, epoch, best_acc, class_names):
    # === CHANGED: 保存完整训练状态，方便继续训练 ===
    torch.save({
        "epoch": epoch,
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
        "best_acc": best_acc,
        "class_names": class_names,
        "model_name": MODEL_NAME,
        "image_size": IMAGE_SIZE,
        "batch_size": BATCH_SIZE,
        "learning_rate": LEARNING_RATE,
    }, path)


def main():
    os.makedirs(REPORTS_DIR, exist_ok=True)      # === CHANGED ===
    os.makedirs(CHECKPOINT_DIR, exist_ok=True)   # === CHANGED ===

    # 1. DEVICE SETUP
    # === CHANGED: Windows 先尝试 CUDA，再 CPU；保留 MPS 兼容 ===
    if torch.cuda.is_available():
        device = torch.device("cuda")
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = torch.device("mps")
    else:
        device = torch.device("cpu")

    print("Using device:", device)

    # 2. TRANSFORMS
    # === CHANGED: 不再直接 Resize((224,224))，改成保持比例 + padding ===
    # === CHANGED: 去掉 RandomHorizontalFlip，网页左右翻转通常不合理 ===
    train_transform = transforms.Compose([
        transforms.Lambda(lambda img: resize_with_padding(img, IMAGE_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406],
                             std=[0.229, 0.224, 0.225]),
    ])

    val_transform = transforms.Compose([
        transforms.Lambda(lambda img: resize_with_padding(img, IMAGE_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406],
                             std=[0.229, 0.224, 0.225]),
    ])

    # 3. DATASETS & DATALOADERS
    train_dir = os.path.join(DATA_DIR, "train")
    val_dir = os.path.join(DATA_DIR, "val")


    print("Loading datasets from:", DATA_DIR)
    train_dataset = datasets.ImageFolder("/Users/celin/Desktop/project2webcrawler/dataset_model/train", transform=train_transform)
    val_dataset = datasets.ImageFolder("/Users/celin/Desktop/project2webcrawler/dataset_model/val", transform=val_transform)

    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE,
                              shuffle=True, num_workers=0)
    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE,
                            shuffle=False, num_workers=0)

    class_names = train_dataset.classes
    num_classes = len(class_names)
    print("Classes:", class_names)

    # === CHANGED: 保存 class names，方便以后 inference 对齐 ===
    with open(CLASS_NAMES_PATH, "w", encoding="utf-8") as f:
        json.dump(class_names, f, ensure_ascii=False, indent=2)

    # 4. LOAD PRETRAINED MODEL & ADAPT HEAD
    model = timm.create_model(MODEL_NAME, pretrained=True)
    model.reset_classifier(num_classes=num_classes)
    model = model.to(device)

    # Optional: freeze backbone, train only head
    for name, param in model.named_parameters():
        if "head" not in name and "fc" not in name and "classifier" not in name:
            param.requires_grad = False

    # 5. LOSS & OPTIMIZER
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=LEARNING_RATE
    )

    # === CHANGED: 支持从 checkpoint 继续训练 ===
    start_epoch = 1
    best_acc = 0.0
    best_labels, best_preds = None, None
    best_epoch = 0

    if RESUME_CHECKPOINT is not None and os.path.exists(RESUME_CHECKPOINT):
        print(f"Resuming from checkpoint: {RESUME_CHECKPOINT}")
        checkpoint = torch.load(RESUME_CHECKPOINT, map_location=device)

        model.load_state_dict(checkpoint["model_state_dict"])
        optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        start_epoch = checkpoint["epoch"] + 1
        best_acc = checkpoint.get("best_acc", 0.0)

        ckpt_class_names = checkpoint.get("class_names", None)
        if ckpt_class_names is not None and ckpt_class_names != class_names:
            print("WARNING: class_names in checkpoint do not match current dataset!")

    # === CHANGED: 如果 history csv 不存在，先写表头 ===
    if not os.path.exists(HISTORY_CSV_PATH):
        with open(HISTORY_CSV_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "epoch",
                "train_loss",
                "train_acc",
                "val_loss",
                "val_acc",
                "is_best"
            ])

    # 6. TRAINING & VALIDATION LOOPS
    def train_one_epoch(epoch):
        model.train()
        running_loss = 0.0
        running_corrects = 0
        total = 0

        for images, labels in train_loader:
            images = images.to(device)
            labels = labels.to(device)

            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)

            loss.backward()
            optimizer.step()

            _, preds = torch.max(outputs, 1)
            running_loss += loss.item() * images.size(0)
            running_corrects += (preds == labels).sum().item()
            total += labels.size(0)

        epoch_loss = running_loss / total
        epoch_acc = running_corrects / total
        print(f"Epoch {epoch}: Train Loss: {epoch_loss:.4f} Acc: {epoch_acc:.4f}")
        return epoch_loss, epoch_acc  # === CHANGED ===

    def evaluate(epoch):
        model.eval()
        running_loss = 0.0
        running_corrects = 0
        total = 0

        all_preds = []
        all_labels = []

        with torch.no_grad():
            for images, labels in val_loader:
                images = images.to(device)
                labels = labels.to(device)

                outputs = model(images)
                loss = criterion(outputs, labels)

                _, preds = torch.max(outputs, 1)
                running_loss += loss.item() * images.size(0)
                running_corrects += (preds == labels).sum().item()
                total += labels.size(0)

                all_preds.append(preds.cpu().numpy())
                all_labels.append(labels.cpu().numpy())

        epoch_loss = running_loss / total
        epoch_acc = running_corrects / total
        print(f"Epoch {epoch}: Val   Loss: {epoch_loss:.4f} Acc: {epoch_acc:.4f}")

        all_preds = np.concatenate(all_preds)
        all_labels = np.concatenate(all_labels)
        return epoch_loss, epoch_acc, all_labels, all_preds  # === CHANGED ===

    # === CHANGED: 每轮都保存 checkpoint、report、confusion matrix ===
    for epoch in range(start_epoch, NUM_EPOCHS + 1):
        train_loss, train_acc = train_one_epoch(epoch)
        val_loss, val_acc, labels, preds = evaluate(epoch)

        is_best = False
        if val_acc > best_acc:
            best_acc = val_acc
            best_labels = labels.copy()
            best_preds = preds.copy()
            best_epoch = epoch
            is_best = True

            save_checkpoint(
                BEST_CHECKPOINT_PATH,
                model,
                optimizer,
                epoch,
                best_acc,
                class_names
            )
            print(f"Saved BEST checkpoint to: {BEST_CHECKPOINT_PATH}")

        # === CHANGED: 每一轮保存一个独立 checkpoint ===
        epoch_checkpoint_path = os.path.join(CHECKPOINT_DIR, f"epoch_{epoch:02d}.pth")
        save_checkpoint(
            epoch_checkpoint_path,
            model,
            optimizer,
            epoch,
            best_acc,
            class_names
        )

        # === CHANGED: 始终覆盖 last checkpoint ===
        save_checkpoint(
            LAST_CHECKPOINT_PATH,
            model,
            optimizer,
            epoch,
            best_acc,
            class_names
        )

        # === CHANGED: 每轮保存 classification report 和 confusion matrix ===
        report_text = classification_report(labels, preds, target_names=class_names)
        cm = confusion_matrix(labels, preds)

        report_path = os.path.join(REPORTS_DIR, f"epoch_{epoch:02d}_classification_report.txt")
        cm_path = os.path.join(REPORTS_DIR, f"epoch_{epoch:02d}_confusion_matrix.txt")

        save_text_report(report_path, report_text)
        save_text_report(cm_path, np.array2string(cm))

        # === CHANGED: 记录历史到 csv ===
        with open(HISTORY_CSV_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                epoch,
                f"{train_loss:.6f}",
                f"{train_acc:.6f}",
                f"{val_loss:.6f}",
                f"{val_acc:.6f}",
                int(is_best)
            ])

    print("\nBest Val Acc:", best_acc)
    print("Best Epoch:", best_epoch)

    # === CHANGED: 最终输出 best epoch 对应的结果，而不是最后一轮 ===
    if best_labels is not None and best_preds is not None:
        best_report = classification_report(best_labels, best_preds, target_names=class_names)
        best_cm = confusion_matrix(best_labels, best_preds)

        best_report_path = os.path.join(REPORTS_DIR, "best_classification_report.txt")
        best_cm_path = os.path.join(REPORTS_DIR, "best_confusion_matrix.txt")

        save_text_report(best_report_path, best_report)
        save_text_report(best_cm_path, np.array2string(best_cm))

        print("\nBest classification report:")
        print(best_report)

        print("Best confusion matrix:")
        print(best_cm)

        print(f"\nSaved best report to: {best_report_path}")
        print(f"Saved best confusion matrix to: {best_cm_path}")
    else:
        print("No best predictions were recorded.")


if __name__ == "__main__":
    main()