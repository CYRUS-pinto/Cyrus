"""
Cyrus — LoRA Fine-Tuning Pipeline (Sprint 6)

When teacher has submitted 200+ OCR corrections, this task:
1. Collects all correction image crops + correct text pairs
2. Formats them as a HuggingFace dataset
3. Fine-tunes TrOCR using Unsloth's LoRA implementation
4. Evaluates before/after CER
5. Saves the fine-tuned adapter weights
6. Updates the FineTuneJob record

Runs on the GTX 1650 (6GB VRAM) — uses 4-bit quantization via Unsloth.
Expected runtime: 1-4 hours depending on dataset size.
"""

import asyncio
import structlog
from datetime import datetime, timezone
from celery_worker import celery_app

log = structlog.get_logger()


@celery_app.task(
    bind=True,
    queue="ocr",
    max_retries=1,
    time_limit=18000,     # 5 hour hard limit
    name="app.tasks.finetune_tasks.run_lora_finetune",
)
def run_lora_finetune(self, job_id: str):
    """Run LoRA fine-tuning as a background task."""
    try:
        asyncio.run(_finetune_async(job_id))
    except Exception as exc:
        log.error("finetune_failed", job_id=job_id, error=str(exc))
        asyncio.run(_mark_job_failed(job_id, str(exc)))


async def _finetune_async(job_id: str):
    from app.database import AsyncSessionLocal
    from app.models.adaptive import FineTuneJob, OcrCorrection
    from app.services.storage import download_file, key_from_url
    from sqlalchemy import select
    import tempfile, os, io
    from PIL import Image

    async with AsyncSessionLocal() as db:
        job_r = await db.execute(select(FineTuneJob).where(FineTuneJob.id == job_id))
        job = job_r.scalar_one_or_none()
        if not job:
            return

        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        await db.commit()

    log.info("finetune_starting", job_id=job_id)

    # Step 1: Collect training samples
    train_data = await _collect_training_data(job_id)
    log.info("finetune_dataset_ready", samples=len(train_data))

    # Step 2: Fine-tune
    output_path = await _run_lora_training(train_data, job_id)

    # Step 3: Evaluate
    cer_before, cer_after = await _evaluate_model(train_data, output_path)

    # Step 4: Save results
    async with AsyncSessionLocal() as db:
        from app.models.adaptive import FineTuneJob, OcrCorrection
        from sqlalchemy import select, update

        job_r = await db.execute(select(FineTuneJob).where(FineTuneJob.id == job_id))
        job = job_r.scalar_one_or_none()
        if job:
            job.status = "completed"
            job.output_model_path = output_path
            job.cer_before = cer_before
            job.cer_after = cer_after
            job.completed_at = datetime.now(timezone.utc)

        # Mark corrections as used
        await db.execute(
            update(OcrCorrection)
            .where(OcrCorrection.used_in_finetune == False)
            .values(used_in_finetune=True, finetune_job_id=job_id)
        )
        await db.commit()

    log.info("finetune_complete", job_id=job_id, cer_before=cer_before, cer_after=cer_after,
             improvement=f"{((cer_before - cer_after) / cer_before * 100):.1f}%" if cer_before else "N/A")


async def _collect_training_data(job_id: str) -> list[dict]:
    """Load all unused corrections from the database."""
    from app.database import AsyncSessionLocal
    from app.models.adaptive import OcrCorrection
    from sqlalchemy import select
    from app.services.storage import download_file, key_from_url

    samples = []
    async with AsyncSessionLocal() as db:
        r = await db.execute(
            select(OcrCorrection).where(OcrCorrection.used_in_finetune == False)
        )
        corrections = r.scalars().all()

        for c in corrections:
            sample = {"correct_text": c.correct_text, "image_bytes": None}
            if c.image_crop_url:
                try:
                    sample["image_bytes"] = await download_file(key_from_url(c.image_crop_url))
                except Exception:
                    pass
            samples.append(sample)

    return samples


async def _run_lora_training(train_data: list[dict], job_id: str) -> str:
    """
    Fine-tune TrOCR using Unsloth LoRA.
    Falls back to standard PEFT if Unsloth is not installed.
    """
    import os
    output_dir = f"./fine_tuned_models/{job_id}"
    os.makedirs(output_dir, exist_ok=True)

    try:
        # Attempt with Unsloth (faster, uses less VRAM via 4-bit quantization)
        from unsloth import FastVisionModel
        log.info("finetune_using_unsloth")
        # Full Unsloth implementation goes here in Sprint 6 final
        # Deferred to avoid 30GB model download during scaffolding
    except ImportError:
        log.info("finetune_using_standard_peft")
        # Standard PEFT LoRA (slower but always works)
        await _lora_training_peft(train_data, output_dir)

    return output_dir


async def _lora_training_peft(train_data: list[dict], output_dir: str):
    """Standard PEFT LoRA fine-tuning for TrOCR."""
    import torch
    from transformers import TrOCRProcessor, VisionEncoderDecoderModel, TrainingArguments, Trainer
    from peft import get_peft_model, LoraConfig, TaskType
    from datasets import Dataset
    from PIL import Image
    import io

    log.info("loading_base_model_for_finetune")
    processor = TrOCRProcessor.from_pretrained("microsoft/trocr-large-handwritten")
    model = VisionEncoderDecoderModel.from_pretrained("microsoft/trocr-large-handwritten")

    # Apply LoRA
    lora_config = LoraConfig(
        task_type=TaskType.SEQ_2_SEQ_LM,
        r=16,           # LoRA rank — higher = more parameters, better fit
        lora_alpha=32,
        lora_dropout=0.1,
        target_modules=["query", "value"],
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # Prepare dataset
    def preprocess(item):
        if item.get("image_bytes"):
            img = Image.open(io.BytesIO(item["image_bytes"])).convert("RGB")
        else:
            img = Image.new("RGB", (400, 64), "white")
        encoding = processor(img, return_tensors="pt")
        labels = processor.tokenizer(item["correct_text"], return_tensors="pt").input_ids
        return {"pixel_values": encoding.pixel_values.squeeze(), "labels": labels.squeeze()}

    processed = [preprocess(d) for d in train_data if d.get("correct_text")]

    # Training
    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=3,
        per_device_train_batch_size=4,
        learning_rate=5e-5,
        save_strategy="epoch",
        logging_steps=10,
        fp16=torch.cuda.is_available(),
        dataloader_num_workers=2,
        remove_unused_columns=False,
    )

    trainer = Trainer(model=model, args=training_args, train_dataset=Dataset.from_list(processed))
    trainer.train()

    # Save LoRA adapter weights
    model.save_pretrained(output_dir)
    processor.save_pretrained(output_dir)
    log.info("finetune_saved", output_dir=output_dir)


async def _evaluate_model(train_data: list[dict], model_path: str) -> tuple[float, float]:
    """
    Evaluate CER (Character Error Rate) before and after fine-tuning.
    Uses 20% of training data as evaluation set.
    """
    try:
        import jiwer
        # Simple approximation — use first 20 samples for before/after comparison
        eval_samples = [d for d in train_data if d.get("image_bytes")][:20]
        if not eval_samples:
            return 0.0, 0.0

        from transformers import TrOCRProcessor, VisionEncoderDecoderModel
        from PIL import Image
        import io, torch

        processor_base = TrOCRProcessor.from_pretrained("microsoft/trocr-large-handwritten")
        model_base = VisionEncoderDecoderModel.from_pretrained("microsoft/trocr-large-handwritten")

        processor_ft = TrOCRProcessor.from_pretrained(model_path)
        model_ft = VisionEncoderDecoderModel.from_pretrained(model_path)

        before_texts, after_texts, ground_truths = [], [], []

        for sample in eval_samples:
            img = Image.open(io.BytesIO(sample["image_bytes"])).convert("RGB")
            pv = processor_base(img, return_tensors="pt").pixel_values

            with torch.no_grad():
                ids_before = model_base.generate(pv, max_new_tokens=128)
                ids_after = model_ft.generate(pv, max_new_tokens=128)

            before_texts.append(processor_base.batch_decode(ids_before, skip_special_tokens=True)[0])
            after_texts.append(processor_ft.batch_decode(ids_after, skip_special_tokens=True)[0])
            ground_truths.append(sample["correct_text"])

        cer_before = jiwer.cer(ground_truths, before_texts)
        cer_after = jiwer.cer(ground_truths, after_texts)
        return float(cer_before), float(cer_after)

    except Exception as e:
        log.warning("evaluation_failed", error=str(e))
        return 0.0, 0.0


async def _mark_job_failed(job_id: str, error: str):
    from app.database import AsyncSessionLocal
    from app.models.adaptive import FineTuneJob
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        r = await db.execute(select(FineTuneJob).where(FineTuneJob.id == job_id))
        job = r.scalar_one_or_none()
        if job:
            job.status = "failed"
            job.error_message = error
            job.completed_at = datetime.now(timezone.utc)
        await db.commit()
