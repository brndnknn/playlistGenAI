import subprocess
import time
import csv
import re
import json
from llm_manager import OllamaManager
from helpers import has_keys

class ModelBenchmark:
    """
    Runs a series of benchmarks by prompting various Ollama models and measuring performance (speed, track validity, etc.).
    """
    def __init__(self, models, prompts, output_csv, spotify_client):
        """
        Initializes the ModelBenchmark with the list of models to test, 
        prompts to use, and references to a SpotifyClient for validation.

        Args:
            models (list): A list of model identifiers (strings) recognized by Ollama.
            prompts (list): A list of prompt strings to test each model with.
            output_csv (str): Path to a CSV file where results will be written. 
                              Set to None if you don't want CSV output.
            spotify_client (SpotifyClient): An instance of SpotifyClient for 
                                            checking track existence.
        """
        self.models = models
        self.prompts = prompts
        self.output_csv = output_csv
        self.results = []
        self.llm_manager = OllamaManager()
        self.spotify_client = spotify_client

    def run_benchmarks(self):
        for model in self.models:
            print(f'Starting model {model}')
            if not self.llm_manager.is_ollama_running(model):
                self.llm_manager.start_ollama_server(model)
            for prompt in self.prompts:
                self.__run_single_test(model, prompt)

        if self.output_csv:
            self.__write_csv()

    def __run_single_test(self, model, prompt):
        """
        Runs a single test of (model, prompt), measuring time, 
        capturing output, and parsing track validity via Spotify.

        Args:
            model (str): The Ollama model name to use.
            prompt (str): The user prompt to pass to the LLM.
        """
        print(f"\n=== Testing model: {model} | Prompt: {prompt} ===")

        start_time = time.time()
        
        try:
            response = self.llm_manager.get_response(model, prompt)
            print(response)
            end_time = time.time()
            runtime = end_time - start_time
            
            # Log/print
            print(f"Time taken: {runtime:.2f} seconds")
            
            valid_tracks , total_tracks, check_results = self.__validate_tracks(response)

            
            # print(f"Model output:\n{json_output}\n")
            print(f"Tracks parsed: {total_tracks}, tracks found on Spotify: {valid_tracks}")

            # Store for summary
            result = {
                "model": model,
                "prompt": prompt,
                "runtime_sec": runtime,
                "output": response,
                "tracks_parsed": total_tracks,
                "tracks_found": valid_tracks,
                "check_results": check_results
            }

            self.results.append(result)
        
        except subprocess.CalledProcessError as e:
            # If there's an error running the command, store that info too
            end_time = time.time()
            runtime = end_time - start_time
            error_msg = e.stderr.strip() if e.stderr else "Unknown error"
            
            print(f"Error calling Ollama with model '{model}': {error_msg}")

            result = {
                "model": model,
                "prompt": prompt,
                "runtime_sec": runtime,
                "output": f"ERROR: {error_msg}",
                "tracks_parsed": 0,
                "tracks_found": 0
            }

            self.results.append(result)

    def __write_csv(self):
        """
        Write results to CSV.
        """
        with open(self.output_csv, "w", newline="", encoding="utf-8") as csvfile:
            fieldnames = [
                "model",
                "prompt",
                "runtime_sec",
                "output",
                "tracks_parsed",
                "tracks_found",
                "check_results"
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.results)

    def __validate_tracks(self, input_text):
        """
        Parses the raw model output and verifies each track 
        against the SpotifyClient.

        Args:
            output_text (str): The text returned by the LLM, 
                               typically lines of \"Title\" - Artist.

        Returns:
            tuple: (valid_count, total_count) indicating how many 
                   tracks were actually found vs. total lines parsed.
        """

        total = 0
        valid = 0
        output_text = ""

        if not isinstance(input_text, str):
            return (0, 0, 'Bad model response')

        try:
            playlist = json.loads(input_text)
            start_time = time.time()
            for track in playlist:
                if has_keys(track, "title", "artist"):
                    title = track["title"]
                    artist = track["artist"]
                    total += 1
                    results = self.spotify_client.track_exists(title, artist)
                    if results[0] == True:
                        valid += 1
                    output_text = output_text + results[1] + '\n'
            end_time = time.time()
            run_time = end_time - start_time
            print(f"Validation time: {run_time:.2f}")

        except json.JSONDecodeError:
            print("JSON error")
            input_text = f"JSON ERROR \n {input_text}"
            return (valid, total, input_text)
        return (valid, total, output_text)
