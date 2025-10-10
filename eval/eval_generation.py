import os
from glob import glob
import cv2
import json
import base64
import time
import math
import traceback
import numpy as np
import sys
from tqdm import tqdm
from PIL import Image
from copy import deepcopy
import concurrent.futures as cf


global task_dic
task_dic = [
    "world_knowledge",
    "commonsense_reasoning",
    "logical_reasoning",
    "mathematical_reasoning",
    "scientific_reasoning",
    "code_to_image",
]


def load_json(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)


def save_json(data, file_path):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


def load_jsonl(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        return [json.loads(line) for line in file]


def save_jsonl(data, file_path):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as file:
        for item in data:
            file.write(json.dumps(item, ensure_ascii=False) + "\n")


def get_response_from_judge_model(prompt, image_file=None):
    """TODO: Configure your own judge model. It is recommended to use Gemini 2.5 Pro."""
    pass


def process_one(item_0):
    item = deepcopy(item_0)
    MAX_RETRY = 15
    try:
        SCORE = 1
        img = item["generated_image"]
        if img == "" or img is None or not os.path.exists(img):
            SCORE = 0
            item["score"] = SCORE
            return item

        for qa in item["question_list"]:
            response_text = ""

            origin_q = qa["question"]
            gt_answer = qa["answer"]

            for attempt in range(MAX_RETRY):
                try:
                    prompt = (
                        "Please answer the following question based on the image:\n"
                        + "Question: "
                        + origin_q
                        + "\n\nYou should only reply yes or no, and do not provide any other extra content."
                    )
                    response_text = get_response_from_judge_model(
                        prompt, image_file=img
                    )
                    if response_text == "" or response_text is None:
                        continue
                    else:
                        break
                except Exception:
                    traceback.print_exc()
                    return None
            response_text = response_text.lower()
            if "yes" in response_text:
                response_text = "yes"
            if "no" in response_text:
                response_text = "no"
            if response_text == gt_answer:
                continue
            else:
                SCORE = 0
                break
        item["score"] = SCORE
        return item

    except Exception as e:
        print("Error:", repr(e))
        return None


def evaluate_accuracy(json_file_list):
    for json_file in json_file_list:
        task = []
        task_correct_num = {}
        data = load_json(json_file)

        for item in data:
            task_type = item["task_type"]
            if task_type not in task_dic:
                task.append(task_type)
                task_correct_num[task_type] = 0
            if item.get("score") == 1:
                task_correct_num[task_type] += 1

        print("===" * 30)
        print("Model:", os.path.basename(json_file).split(".")[0])
        for task in task_dic:
            acc = task_correct_num[task] / 100
            print("---" * 20)
            print(f"Task: {task}, Accuracy: {task_correct_num[task]}/100 = {acc:.4f}")
        total_correct_num = sum(task_correct_num.values())
        total_acc = total_correct_num / 600.0
        print("---" * 20)
        print(f"Total Accuracy: {total_correct_num}/600 = {total_acc:.4f}")


if __name__ == "__main__":
    task_json_list = {
        "model_name_1": "file_to_evaluate_1.json",
        "model_name_2": "file_to_evaluate_2.jsonl",
    }
    RES_JSON_DIR = "path_to_save_results"
    res_json_list = []
    for model_name in task_json_list:

        json_file = task_json_list[model_name]

        if json_file.endswith(".jsonl"):
            data = load_jsonl(json_file)
        elif json_file.endswith(".json"):
            data = load_json(json_file)

        num_workers = 16
        new_data = []

        with cf.ProcessPoolExecutor(max_workers=num_workers) as ex:
            futures = [ex.submit(process_one, item) for item in data]
            for fut in tqdm(cf.as_completed(futures), total=len(futures)):
                new_data.append(fut.result())

        res_json_file = os.path.join(RES_JSON_DIR, f"{model_name}.json")
        save_json(new_data, res_json_file)
        res_json_list.append(res_json_file)

    evaluate_accuracy(res_json_list)
