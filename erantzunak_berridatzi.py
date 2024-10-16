import transformers
import torch
import argparse
import json
import os

def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--model_type", type=str, required=True, choices=["openchat", "llama-8b"],
        help="Model type to be fine-tuned."
    )
    parser.add_argument(
        "--root", type=str, default="/gaueko0/users/ietxarri010/GrAL_Irene/okvqa", help="Path to the OkVqa prediction files."
    )

    args = parser.parse_args()
    return args

def main():
    print("Parsing args...")
    args = parse_args()

    # Load jsons
    with open(os.path.join(args.root, 'train', f'annotations_train.json'), "r") as f:
            train = json.load(f)

    #with open(os.path.join(args.root, 'val', f'annotations_val.json'), "r") as f:
    #        val = json.load(f)

    # Create output files
    train_values = f"./output/values/train_values.txt"
    #val_values = f"./output/values/train_values.txt"

    os.makedirs(os.path.dirname(train_values), exist_ok=True)
    #os.makedirs(os.path.dirname(val_values), exist_ok=True)

    with open(train_values, 'w') as f: pass
    #with open(val_values, 'w') as f: pass
       

    if args.model_type == "llama-8b":
        model_id = "meta-llama/Meta-Llama-3.1-8B-Instruct"
        pipeline = transformers.pipeline(
            "text-generation",
            model=model_id,
            model_kwargs={"torch_dtype": torch.bfloat16},
            device_map="auto",
        )
        messages = [
            {"role": "system", "content": "You are a pirate chatbot who always responds in pirate speak!"},
            {"role": "user", "content": "Who are you?"},
        ]
        outputs = pipeline(
            messages,
            max_new_tokens=256,
        )
        print(outputs[0]["generated_text"][-1])
    
    elif args.model_type == "openchat":
        pipeline = transformers.pipeline("text-generation", model="openchat/openchat-3.5-0106", torch_dtype=torch.bfloat16, device_map="auto")

        for ann in train:
            question = ann['question']
            answers = ann['answer']

            with open(train_values, 'a') as f:
                 f.write(f'{question}')
            
            for answer in answers:
                prompt = f"Question: {question}\nAnswer: {answer}\nPlease rewrite the answer using synonyms or rephrasing."
                result = pipeline(prompt, max_length=50, truncation=True, num_return_sequences=1) 
                #print(result[0]['generated_text'], "\n")

                with open(train_values, 'a') as f:
                    f.write(f' {answer} --> {result[0]['generated_text']}')

if __name__ == "__main__":
    main()