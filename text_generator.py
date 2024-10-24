import transformers
import torch
import argparse
import json
import os
import copy
import time
from transformers import AutoModelForCausalLM, AutoTokenizer
import bitsandbytes as bnb
from huggingface_hub import login
from progressbar import ProgressBar
import requests


def create_prompt(question, answer, is_llama=False):
    if is_llama:
        return [
            {"role": "system", "content": "You are an assistant that provides rephrased answers using one-word synonyms or a few words equivalent term."},
            {"role": "user", "content": f"Question: {question}\n"
                                        f"Answer: {answer}\n"
                                        "If the answer is a proper noun, keep it unchanged. "
                                        "If you can confidently provide a one-word synonym or equivalent term, do so. "
                                        "Otherwise, leave the answer unchanged. "
                                        "Do not include any additional text or explanation."},
        ]
    else:
        return f"Question: {question}\n" \
               f"Answer: {answer}\n" \
               "If the answer is a proper noun, keep it unchanged. " \
               "If you can confidently provide a one-word synonym or equivalent term, do so. " \
               "Otherwise, leave the answer unchanged. Do not include any additional text or explanation."


def get_batch_prompts(annotations, model_name):
    batch_prompts = []
    is_llama = "llama" in model_name  
    for ann in annotations:
        question = ann["question"]
        answers = [str(ans["answer"]) for ans in ann["answers"]]
        for answer in answers:
            prompt = create_prompt(question, answer, is_llama)
            batch_prompts.append(prompt)
    return batch_prompts


def replace_info(data, results):
    data_ = copy.deepcopy(data)
    for idx, ann in enumerate(data["annotations"]):
        for answer_id in range(len(ann["answers"])):
            result = results.pop(0)
            data_["annotations"][idx]["answers"][answer_id]["answer"] = result
    return data_

class ComputeResults:
    def __init__(self, model_name, token=None):
        """
        Initializes the class with the model type and the method you want to use (API or pipeline).

        :param model_name: Name of the model to use.
        :param use_api: If True, uses the Ollama API; if False, uses the transformers pipeline.
        :param token: Hugging Face token (only required if using the llama model).
        """
        self.model_name = model_name
        self.token = token
        self.is_llama = "llama" in model_name
        self.pipeline = self.load_pipeline()  

    def load_pipeline(self):
        """
        Loads the transformers pipeline for the especified model.
        """
        if "llama" in self.model_name:
            if self.token:
                # Login to Hugging Face
                assert self.token != None, "Unable to login Hugging Face, please provide a HF token."
                login(self.token)

            if self.model_name == "llama3.1:8b":
                model_id = "meta-llama/Meta-Llama-3.1-8B-Instruct"
                model = "meta-llama/Meta-Llama-3.1-8B-Instruct"

            elif self.model_name == "llama3.1:70b":
                model_id = "meta-llama/Llama-3.1-70B-Instruct"
                model = AutoModelForCausalLM.from_pretrained(
                    model_id,
                    load_in_8bit=True,  # 8 bits cuantization
                    device_map="auto",  
                    torch_dtype=torch.bfloat16,  
                )

            tokenizer = AutoTokenizer.from_pretrained(model_id)
            
            return transformers.pipeline(
                "text-generation",
                model=model,
                tokenizer=tokenizer,
                torch_dtype=torch.bfloat16, 
                device_map="auto",
                pad_token_id=50256,
            )

        else:  # openchat
            return transformers.pipeline(
                "text-generation", 
                model="openchat/openchat-3.5-0106", 
                torch_dtype=torch.bfloat16, 
                device_map="auto"
            )


    def generate(self, batch_prompts, batch_size=32):
        """
        Main method for result generation. Depending on the initial configuration uses the API or the pipeline.
        """
        results = []
        bar = ProgressBar(max_value=1 + len(batch_prompts))

        for i in range(0, len(batch_prompts), batch_size):
            batch = batch_prompts[i:i+batch_size]

            outputs = self.pipeline(batch, max_new_tokens=10, truncation=True)

            for output in outputs:
                generated_text = output if self.use_api else output[0]['generated_text']
                result, answer = self.get_result(generated_text)
                processed_result = self.result_processing(result, answer)
                results.append(processed_result)

            bar.update(i)
        bar.finish()
        return results
    
    def get_result(self, generated_text):
        """
        Processes the generated text to get the final result and the original answer.
        """
        if self.is_llama:
            user_text = generated_text[1]['content']  
            return generated_text[-1]['content'], user_text.split("Answer: ")[1].split("\n")[0]
        else:
            print(generated_text)
            return "", ""
    
    def result_processing(self, result, answer, word_limit=8):
        """
        Discards the longest results and replaces them with the orginal answer.
        """
        if len(result.split()) > word_limit:
            return answer
        return result 


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model_name", type=str, required=True, choices=["openchat", "llama3.1:8b", "llama3.1:70b"],
        help="Model name to use."
    )
    parser.add_argument(
        "--root", type=str, default="/gaueko0/users/ietxarri010/GrAL_Irene/okvqa", help="Path to the OkVqa prediction files."
    )
    parser.add_argument(
        "--token", type=str, default=None, help="HuggingFace login token"
    )
    args = parser.parse_args()
    return args


def main():
    print("Parsing args...")
    args = parse_args()

    # Load jsons
    with open(os.path.join(args.root, 'train', f'annotations_train.json'), "r") as f: 
      train = json.load(f)
      train["annotations"] = train["annotations"][:20]
    #with open(os.path.join(args.root, 'val', f'annotations_val.json'), "r") as f: 
    #  val = json.load(f)
    #  val["annotations"] = val["annotations"][:5]

    # Get prompts
    train_batch_prompts = get_batch_prompts(train["annotations"], args.model_name)
    #val_batch_prompts = get_batch_prompts(val["annotations"], args.model_type)
    
    # Create class instance
    compute = ComputeResults(
        model_name=args.model_name,
        token=args.token 
    )

    # Train 
    train_results = compute.generate(train_batch_prompts)
    #train_ = replace_info(train, train_results)
    #train_path = os.path.join(args.root, 'train', 'annotations_train_.json')
    #os.makedirs(os.path.dirname(train_path), exist_ok=True)
    #with open(train_path, 'w') as json_file:
    #    json.dump(train_, json_file, indent=4)
    print(f"Train set finnished!\n")

    """

    # Val 
    val_results = compute_results(pipeline, val_batch_prompts)
    val_ = replace_info(val, val_results)
    val_path = os.path.join(args.root, 'val', 'annotations_val_.json')
    os.makedirs(os.path.dirname(val_path), exist_ok=True)
    with open(val_path, 'w') as json_file:
        json.dump(val_, json_file, indent=4)
    print("Val set finnished!\n")
    """

if __name__ == "__main__":
    main()