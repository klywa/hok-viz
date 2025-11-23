import argparse
import json
import os
from parser import MatchParser
from renderer import MatchRenderer

def process_batch(input_file, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Determine assets directory (relative to this script)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    assets_dir = os.path.join(project_root, "assets")

    parser = MatchParser()
    renderer = MatchRenderer(assets_dir=assets_dir)
    
    print(f"Processing {input_file}...")
    
    count = 0
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                match_id = data.get('id')
                content = data.get('content') or data.get('match_info') # Handle possible keys
                
                if not match_id or not content:
                    print(f"Skipping line: missing id or content")
                    continue
                
                print(f"Rendering match {match_id}...")
                match_state = parser.parse(content)
                img = renderer.render(match_state)
                
                out_path = os.path.join(output_dir, f"{match_id}.png")
                img.save(out_path)
                print(f"Saved to {out_path}")
                count += 1
            except json.JSONDecodeError:
                print("Skipping invalid JSON line")
            except Exception as e:
                print(f"Error processing line: {e}")
    
    print(f"Batch processing complete. {count} images generated.")

if __name__ == "__main__":
    arg_parser = argparse.ArgumentParser(description="HOK-Viz Batch Processor")
    arg_parser.add_argument("--input", required=True, help="Path to input .jsonl file")
    arg_parser.add_argument("--output", required=True, help="Output directory")
    
    args = arg_parser.parse_args()
    process_batch(args.input, args.output)

