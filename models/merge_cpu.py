#!/usr/bin/env python3
import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

print("Loading base model onto CPU RAM...")
base = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen2.5-Coder-1.5B-Instruct",
    torch_dtype=torch.float16,
    device_map="cpu",
    low_cpu_mem_usage=True
)
print("Loading LoRA adapter...")
model = PeftModel.from_pretrained(base, "D:\RAG-Agent\models\lora_adapters\stem-expert")
print("Merging weights on CPU...")
merged = model.merge_and_unload()

print("Saving merged model to D:\RAG-Agent\models\merged_checkpoint...")
merged.save_pretrained("D:\RAG-Agent\models\merged_checkpoint")
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-Coder-1.5B-Instruct")
tokenizer.save_pretrained("D:\RAG-Agent\models\merged_checkpoint")
print("Merge complete!")
