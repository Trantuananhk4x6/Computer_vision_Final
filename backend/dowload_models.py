#!/usr/bin/env python3
import os
import sys
import requests
import argparse
from pathlib import Path

def download_file(url, destination):
    """Download a file from URL to destination with progress bar"""
    try:
        print(f"Downloading {url} to {destination}")
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        block_size = 1024  # 1 Kibibyte
        downloaded = 0
        
        # Ensure the directory exists
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        
        with open(destination, 'wb') as file:
            for data in response.iter_content(block_size):
                downloaded += len(data)
                file.write(data)
                
                # Update progress bar
                done = int(50 * downloaded / total_size)
                sys.stdout.write("\r[%s%s] %d%%" % ('=' * done, ' ' * (50-done), int(100 * downloaded / total_size)))
                sys.stdout.flush()
        
        print("\nDownload complete.")
        return True
    except Exception as e:
        print(f"Error downloading file: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Download model files for YOLOv8 and DeepSORT')
    parser.add_argument('--deepsort-only', action='store_true', help='Only download DeepSORT model')
    args = parser.parse_args()
    
    # Define model URLs and destinations
    models = {
        'deepsort': {
            'url': 'https://drive.google.com/uc?id=1_qzJ0XjmEoyaZFTlbzRQ2ibpxUh_U-XS',
            'dest': 'deep_sort_pytorch/deep_sort/deep/checkpoint/ckpt.t7'
        }
    }
    
    # Download DeepSORT model
    if not os.path.exists(models['deepsort']['dest']):
        success = download_file(models['deepsort']['url'], models['deepsort']['dest'])
        if not success:
            print("Failed to download DeepSORT model.")
    else:
        print(f"DeepSORT model already exists at {models['deepsort']['dest']}")
    
    print("All required models have been downloaded.")

if __name__ == "__main__":
    main()