#!/usr/bin/env python3

import argparse
import sys
import os
import time
import json
from pathlib import Path
from Muxer import Muxer
from concurrent.futures import ThreadPoolExecutor
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class FileHandler(FileSystemEventHandler):
    def __init__(self, args):
        self.args = args
        
    def on_created(self, event):
        if not event.is_directory:
            input_directory = os.path.dirname(event.src_path)
            process_directory(input_directory, self.args)

def process_file(image, video, args, input_dir):
    input_image = os.path.join(input_dir, image)
    
    fname = f"{Path(image).with_suffix('')}"
    output_subdirectory = args.output_directory
    if output_subdirectory is not None:
        output_subdirectory = f"{Path(os.path.join(output_subdirectory, os.path.dirname(fname))).resolve()}"
        if os.path.exists(output_subdirectory) is False:
            os.makedirs(output_subdirectory)

    if video is None:
        # If no video, just copy the image to output directory
        output_path = os.path.join(output_subdirectory, os.path.basename(input_image))
        import shutil
        shutil.copy2(input_image, output_path)
    else:
        input_video = os.path.join(input_dir, video)
        Muxer(
            image_fpath=input_image,
            video_fpath=input_video,
            output_directory=output_subdirectory,
            delete_video=args.delete_video,
            delete_temp=not args.keep_temp,
            overwrite=args.overwrite,
            verbose=args.verbose,
        ).mux()
    
    # Record processed files
    processed_files = load_processed_files()
    processed_files[input_image] = {
        "video": input_video if video else None,
        "timestamp": time.time()
    }
    save_processed_files(processed_files)
    print("=" * 25)
    

import threading
_file_lock = threading.Lock()

def load_processed_files():
    processed_file = "processed_files.json"
    with _file_lock:
        if os.path.exists(processed_file):
            with open(processed_file, 'r') as f:
                return json.load(f)
        return {}

def save_processed_files(processed_files):
    with _file_lock:
        with open("processed_files.json", 'w') as f:
            json.dump(processed_files, f, indent=2)

def process_subdirectory(input_directory, args):
    files = [file for file in os.listdir(input_directory) if
             os.path.isfile(os.path.join(input_directory, file))]

    # Load processed files
    processed_files = load_processed_files()

    _videos = [
        f
        for f in files
        if os.path.isfile(os.path.join(input_directory, f))
            and Path(f).suffix.lower() in [".mp4", ".mov"]
    ]
    images = [
        f
        for f in files
        if os.path.isfile(os.path.join(input_directory, f))
            and Path(f).suffix.lower() in [".heic", ".heif", ".avif", ".jpg", ".jpeg"]
    ]
    
    videos = []
    for _video in _videos:
        videos.append(f"{Path(_video)}")

    # Process images first
    tasks = []
    image_bases = set()
    for image in images:
        image_path = os.path.join(input_directory, image)
        # Skip if already processed
        if image_path in processed_files:
            continue
            
        fname = f"{Path(image).with_suffix('')}"
        image_bases.add(fname)
        for ext in [".mp4", ".mov", ".MP4", ".MOV"]:
            videoName = fname + ext
            if videoName in videos:
                video = videos.pop(videos.index(fname + ext))
                tasks.append((image, video))
                break
        else:
            tasks.append((image, None))

    # Process remaining videos that have no matching images
    if args.output_directory is not None:
        for video in videos:
            video_base = f"{Path(video).with_suffix('')}"
            if video_base not in image_bases:
                video_path = os.path.join(input_directory, video)
                output_path = os.path.join(args.output_directory, video)
                if not os.path.exists(args.output_directory):
                    os.makedirs(args.output_directory)
                import shutil
                shutil.copy2(video_path, output_path)

    for image, video in tasks:
        process_file(image, video, args, input_directory)

def process_directory(input_directory, args):
    # Get all subdirectories including root
    subdirs = [input_directory]
    for root, dirs, _ in os.walk(input_directory):
        for d in dirs:
            subdirs.append(os.path.join(root, d))
            
    # Process subdirectories using thread pool
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(process_subdirectory, subdir, args) for subdir in subdirs]
        for future in futures:
            future.result()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="MotionPhoto2",
        description="Mux HEIC and JPG Live Photos into Google/Samsung Motion Photos",
    )

    parser.add_argument("-ii", "--input-image", help="Input file image (.heic, .jpg)")
    parser.add_argument("-iv", "--input-video", help="Input file video (.mov, .mp4)")
    parser.add_argument("-of", "--output-file", help="Output filename of Live Photos")

    parser.add_argument(
        "-id", "--input-directory", help="Mux all the photos and video in directory"
    )
    parser.add_argument(
        "-od",
        "--output-directory",
        help="Store all the Live Photos into dedicated directory",
    )

    parser.add_argument(
        "-dv",
        "--delete-video",
        action="store_true",
        help="Automatically delete video after muxing",
    )
    parser.add_argument(
        "-kt",
        "--keep-temp",
        action="store_true",
        help="Keep temp file used during muxing",
    )
    parser.add_argument(
        "-o",
        "--overwrite",
        action="store_true",
        help="Overwrite the original image file as output Live Photos",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose muxing")

    args = parser.parse_args()

    if args.input_directory is not None and (
            args.input_image is not None or args.input_video is not None
    ):
        print("[ERROR] Input directory cannot be use with input-image or input-video")
        sys.exit(1)

    if args.input_directory is None:
        if args.input_image is None or args.input_video is None:
            print("[ERROR] Please provide both input image/video or input directory")
            sys.exit(1)

    if args.output_directory is not None and args.overwrite is True:
        print("[ERROR] Output directory cannot be use overwrite option")
        sys.exit(1)

    if args.output_file is not None and args.overwrite is True:
        print("[ERROR] Output file cannot be use overwrite option")
        sys.exit(1)

    if args.overwrite is True or args.delete_video is True:
        text = f"[WARNING] Make sure to have a backup of your image and/or video file (overwrite={args.overwrite}, delete-video={args.delete_video})"
        confirmation = input(f"{text}\nContinue? [Y/n] ")
        if len(confirmation) > 0 and confirmation[0].lower() == "n":
            sys.exit(1)

    if args.output_directory is not None:
        output_directory = f"{Path(args.output_directory).resolve()}"
        if os.path.exists(output_directory) is False:
            os.mkdir(output_directory)

    if args.input_directory is not None:
        input_directory = f"{Path(args.input_directory).resolve()}"
        
        # Initial processing of existing files
        process_directory(input_directory, args)
        
        # Set up directory monitoring
        event_handler = FileHandler(args)
        observer = Observer()
        observer.schedule(event_handler, input_directory, recursive=True)
        observer.start()
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()

    else:
        input_image = args.input_image
        # Check if single file was already processed
        processed_files = load_processed_files()
        if input_image in processed_files:
            print(f"File {input_image} was already processed")
            sys.exit(0)
            
        Muxer(
            image_fpath=input_image,
            video_fpath=args.input_video,
            output_fpath=args.output_file,
            output_directory=args.output_directory,
            delete_video=args.delete_video,
            delete_temp=not args.keep_temp,
            overwrite=args.overwrite,
            verbose=args.verbose,
        ).mux()
        
        # Record processed single file
        processed_files[input_image] = {
            "video": args.input_video,
            "timestamp": time.time()
        }
        save_processed_files(processed_files)
