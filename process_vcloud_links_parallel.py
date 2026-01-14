#!/usr/bin/env python3
"""
Script to process vcloud.zip links in a JSON file, converting them to start parameters.
Features:
- Progress saving and resumption
- Parallel processing with multiple workers
- Error handling for failed links
- Minimal output showing progress
- Uses fresh HTTP clients like the working individual resolver
- Thread-safe progress saving
"""

import sys
import json
import httpx
import re
import base64
import os
import time
from urllib.parse import urlparse, parse_qs, unquote_plus
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
from datetime import datetime, timedelta
import threading

# Set up logging to only show warnings and errors
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global lock for thread-safe file writing
progress_lock = threading.Lock()


def get_hubcloud_url_from_vcloud(vcloud_url):
    """
    Replicate the functionality of vcloud_resolver.sh to get to the hubcloud URL with re parameter
    Uses fresh HTTP client like the working individual resolver
    Handles both regular vcloud.zip links and API-style links
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:143.0) Gecko/20100101 Firefox/143.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Priority': 'u=0, i'
    }

    # Check if this is an API-style URL (contains /api/)
    if '/api/' in vcloud_url:
        print(f"Processing API-style URL: {vcloud_url}")
        # For API-style URLs, we need to get the actual vcloud.zip URL from the HTML
        with httpx.Client() as client:
            response = client.get(vcloud_url, headers=headers)
            html_response = response.text

            # Extract the actual vcloud.zip URL from the HTML
            # Look for href attributes containing vcloud.zip
            actual_url_match = re.search(r'href="(https://vcloud\.zip/[^\s\'\"<>]+)"', html_response)
            if actual_url_match:
                actual_vcloud_url = actual_url_match.group(1)
                print(f"Found actual vcloud URL: {actual_vcloud_url}")
                # Now process the actual URL
                vcloud_url = actual_vcloud_url
            else:
                raise ValueError(f"Could not find actual vcloud.zip URL in API response for {vcloud_url}")

    # Create a fresh client for each URL like the working individual resolver
    with httpx.Client() as client:
        # Step 1: GET the vcloud link to get the HTML
        response = client.get(vcloud_url, headers=headers)
        html_response = response.text

        # Step 2: Extract the cdn.ampproject.org URL from the HTML
        amp_url_match = re.search(r'https://[^\s"<>\']*\.cdn\.ampproject\.org[^\s"<>\']*', html_response)

        if not amp_url_match:
            all_amp_urls = re.findall(r'https://[^\s"<>\']*ampproject[^\s"<>\']*', html_response)
            if all_amp_urls:
                amp_url = all_amp_urls[0]  # Use the first one found
            else:
                raise ValueError("Could not find cdn.ampproject.org URL in the response")
        else:
            amp_url = amp_url_match.group(0)

        # Step 3: Decode the base64 string after /foo/ to get the URL with id parameter
        foo_match = re.search(r'foo/([^/]*)', amp_url)

        if not foo_match:
            raise ValueError("Could not extract base64 string after /foo/")

        base64_part = foo_match.group(1)
        try:
            decoded_bytes = base64.b64decode(base64_part)
            decoded_url = decoded_bytes.decode('utf-8')
        except Exception as e:
            raise ValueError(f"Could not decode base64 string: {str(e)}")

        # Step 4: Extract the id parameter from the decoded URL
        # Extract id parameter directly from the URL string to preserve + signs
        id_match = re.search(r'[?&]id=([^&]*)', decoded_url)
        if not id_match:
            raise ValueError("Could not extract id parameter from decoded URL")

        id_value = id_match.group(1)

        # Step 5: Construct the hubcloud.one/tg//go?id= URL and GET it
        hubcloud_url = f"https://hubcloud.one/tg//go?id={id_value}"

        # Perform the request with follow_redirects=True to get the final URL like the bash script does
        final_response = client.get(hubcloud_url, headers=headers, follow_redirects=True)
        final_url = str(final_response.url)

        # Check if we got redirected to a Google "sorry" page (captcha)
        if "google.com/sorry" in final_url:
            # Extract the continue parameter which contains the actual destination
            continue_match = re.search(r'continue=([^&]*)', final_url)
            if continue_match:
                continue_url_encoded = continue_match.group(1)
                import urllib.parse
                actual_url = urllib.parse.unquote(continue_url_encoded)

                # Now process the actual URL
                # Check for /re2/ in the actual URL
                re2_match = re.search(r're2/([^/]+)', actual_url)

                if re2_match:
                    base64_re2 = re2_match.group(1)
                    # URL decode the base64 string to restore + signs
                    base64_re2 = unquote_plus(base64_re2)
                    try:
                        decoded_re2_bytes = base64.b64decode(base64_re2)
                        decoded_re2 = decoded_re2_bytes.decode('utf-8')
                    except Exception as e:
                        raise ValueError(f"Could not decode base64 string after /re2/: {str(e)}")

                    # Step 7: Decode the base64 string in the r parameter of the resulting URL
                    # Extract r parameter directly from the URL string to preserve + signs
                    r_match = re.search(r'[?&]r=([^&]*)', decoded_re2)
                    if not r_match:
                        raise ValueError("Could not extract r parameter")

                    r_param = r_match.group(1)
                    # URL decode the r parameter to restore + signs
                    r_param = unquote_plus(r_param)
                    try:
                        decoded_r_bytes = base64.b64decode(r_param)
                        decoded_r = decoded_r_bytes.decode('utf-8')
                    except Exception as e:
                        raise ValueError(f"Could not decode r parameter: {str(e)}")

                    return decoded_r
                else:
                    # If no /re2/ in the actual URL, look for r parameter
                    r_match = re.search(r'[?&]r=([^&]*)', actual_url)
                    if r_match:
                        r_param = r_match.group(1)
                        # URL decode the r parameter to restore + signs
                        r_param = unquote_plus(r_param)
                        try:
                            decoded_r_bytes = base64.b64decode(r_param)
                            decoded_r = decoded_r_bytes.decode('utf-8')
                        except Exception as e:
                            raise ValueError(f"Could not decode r parameter: {str(e)}")

                        return decoded_r
                    else:
                        # If no r parameter, return the actual URL as-is
                        return actual_url
            else:
                raise ValueError("Could not extract continue URL from Google captcha page")

        # Original logic for non-captcha pages
        re2_match = re.search(r're2/([^/]+)', final_url)

        if re2_match:
            base64_re2 = re2_match.group(1)
            # URL decode the base64 string to restore + signs
            base64_re2 = unquote_plus(base64_re2)
            try:
                decoded_re2_bytes = base64.b64decode(base64_re2)
                decoded_re2 = decoded_re2_bytes.decode('utf-8')
            except Exception as e:
                raise ValueError(f"Could not decode base64 string after /re2/: {str(e)}")

            # Step 7: Decode the base64 string in the r parameter of the resulting URL
            # Extract r parameter directly from the URL string to preserve + signs
            r_match = re.search(r'[?&]r=([^&]*)', decoded_re2)
            if not r_match:
                raise ValueError("Could not extract r parameter")

            r_param = r_match.group(1)
            # URL decode the r parameter to restore + signs
            r_param = unquote_plus(r_param)
            try:
                decoded_r_bytes = base64.b64decode(r_param)
                decoded_r = decoded_r_bytes.decode('utf-8')
            except Exception as e:
                raise ValueError(f"Could not decode r parameter: {str(e)}")

            return decoded_r
        else:
            # If no /re2/, look for base64 in the r parameter of the final URL directly
            # Extract r parameter directly from the final URL
            r_match = re.search(r'[?&]r=([^&]*)', final_url)
            if r_match:
                r_param = r_match.group(1)
                # URL decode the r parameter to restore + signs
                r_param = unquote_plus(r_param)
                try:
                    decoded_r_bytes = base64.b64decode(r_param)
                    decoded_r = decoded_r_bytes.decode('utf-8')
                except Exception as e:
                    raise ValueError(f"Could not decode r parameter: {str(e)}")

                return decoded_r
            else:
                # If no r parameter, return the final URL as-is
                return final_url


def follow_redirect_chain_and_extract_start(decoded_r_url):
    """
    Follow the redirect chain from the decoded_r URL and extract the start parameter
    Uses fresh HTTP client like the working individual resolver
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:143.0) Gecko/20100101 Firefox/143.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Priority': 'u=0, i'
    }

    current_url = decoded_r_url
    max_redirects = 10
    redirect_count = 0

    # Create a fresh client for each redirect chain like the working individual resolver
    with httpx.Client() as client:
        while redirect_count < max_redirects:
            response = client.get(current_url, headers=headers, follow_redirects=False)
            location = response.headers.get('Location')

            if location:
                current_url = location
                redirect_count += 1
                continue  # Continue the loop to follow the next redirect

            # Check for meta refresh in HTML content
            meta_refresh_match = re.search(r'url=([^\'"&\s<>]+)', response.text)

            if meta_refresh_match:
                import urllib.parse
                meta_url = urllib.parse.unquote(meta_refresh_match.group(1))
                # If the URL is relative, make it absolute
                if not meta_url.startswith(('http://', 'https://')):
                    base_url = str(response.url)
                    parsed_base = urlparse(base_url)
                    meta_url = f"{parsed_base.scheme}://{parsed_base.netloc}{meta_url}"

                current_url = meta_url
                redirect_count += 1
                continue  # Continue the loop to follow the next redirect

            # No more redirects
            final_response_php = response
            final_redirect_url = str(response.url)
            break
        else:
            # If we hit the max redirects limit
            final_response_php = response
            final_redirect_url = str(response.url)

        # Extract from the final redirect URL after all redirects
        final_parsed = urlparse(final_redirect_url)
        final_query = parse_qs(final_parsed.query)
        start_param_list = final_query.get('start', [])

        if start_param_list:
            return start_param_list[0]
        else:
            # Check if start parameter is in the HTML content
            start_match = re.search(r'start=([^\'"&\s<>]+)', final_response_php.text)
            if start_match:
                import urllib.parse
                return urllib.parse.unquote(start_match.group(1))
            else:
                # As a last resort, check the final URL directly
                final_url_start_match = re.search(r'[?&]start=([^&\s\'"<>#]+)', final_redirect_url)
                if final_url_start_match:
                    import urllib.parse
                    return urllib.parse.unquote(final_url_start_match.group(1))
                else:
                    raise ValueError("Could not extract start parameter from any source")


def process_vcloud_link(vcloud_url):
    """
    Process a single vcloud URL and return the start parameter
    Uses fresh HTTP clients like the working individual resolver
    """
    try:
        # Step 1: Use vcloud_resolver.sh logic to get to the hubcloud URL
        decoded_r_url = get_hubcloud_url_from_vcloud(vcloud_url)

        # Add a delay between the two phases to improve success rate
        time.sleep(5)

        # Step 2: Use debug_new_url.py logic to follow the redirect chain and extract start parameter
        start_param = follow_redirect_chain_and_extract_start(decoded_r_url)

        return start_param
    except Exception as e:
        print(f"Error processing {vcloud_url}: {e}")
        return None


def find_vcloud_links(data, links_list=None):
    """
    Recursively find all vcloud.zip links in the JSON data
    Returns a list of tuples: (path_to_link, link_url)
    """
    if links_list is None:
        links_list = []

    if isinstance(data, dict):
        for key, value in data.items():
            if key == "url" and isinstance(value, str) and "vcloud.zip" in value:
                # Find the parent object that contains this URL
                path = [data]
                links_list.append((path, value))
            elif isinstance(value, (dict, list)):
                find_vcloud_links(value, links_list)
    elif isinstance(data, list):
        for item in data:
            find_vcloud_links(item, links_list)

    return links_list


def update_json_with_results(data, results_map):
    """
    Update the JSON data with the processed results
    """
    def update_recursive(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key == "url" and isinstance(value, str) and "vcloud.zip" in value and value in results_map:
                    # Replace the URL with the start parameter
                    obj[key] = results_map[value]
                elif isinstance(value, (dict, list)):
                    update_recursive(value)
        elif isinstance(data, list):
            for item in obj:
                update_recursive(item)

    update_recursive(data)


def load_progress(progress_file):
    """
    Load progress from a file
    """
    if os.path.exists(progress_file):
        # Check if file is empty
        if os.path.getsize(progress_file) == 0:
            return {"processed": {}}
        with open(progress_file, 'r') as f:
            return json.load(f)
    return {"processed": {}}


def save_progress(progress_file, progress_data):
    """
    Save progress to a file
    """
    with progress_lock:  # Thread-safe file writing
        with open(progress_file, 'w') as f:
            json.dump(progress_data, f, indent=2)


def process_json_file(input_file, num_workers=5):
    """
    Process the JSON file with vcloud.zip links
    Uses parallel processing with multiple workers
    """
    # Define progress and output file names
    base_name = os.path.splitext(input_file)[0]
    progress_file = f"{base_name}_progress.json"
    output_file = f"{base_name}_output.json"

    # Load the JSON data
    with open(input_file, 'r') as f:
        data = json.load(f)

    # Find all vcloud.zip links
    print("Finding vcloud.zip links in JSON data...")
    vcloud_links = find_vcloud_links(data)

    # Extract just the URLs for processing
    vcloud_urls = [link[1] for link in vcloud_links]
    print(f"Found {len(vcloud_urls)} vcloud.zip links to process")

    # Load previous progress
    progress = load_progress(progress_file)

    # Determine which links still need processing
    unprocessed_urls = [url for url in vcloud_urls if url not in progress["processed"]]
    print(f"Unprocessed links: {len(unprocessed_urls)}")

    # Calculate statistics
    total_links = len(vcloud_urls)
    processed_count = len(progress["processed"])
    remaining_count = len(unprocessed_urls)

    start_time = time.time()
    completed_tasks = 0

    # Process the unprocessed links with multiple workers
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        # Submit tasks for unprocessed URLs
        future_to_url = {executor.submit(process_vcloud_link, url): url for url in unprocessed_urls}

        # Process completed tasks
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                result = future.result()

                if result is not None:
                    # Success - store the result
                    progress["processed"][url] = result

            except Exception as e:
                # Skip failed links - they will be treated as new in the next run
                print(f"Exception processing {url}: {e}")
                pass

            # Save progress after each completed task
            save_progress(progress_file, progress)

            # Update statistics
            completed_tasks += 1
            elapsed_time = time.time() - start_time
            avg_time_per_task = elapsed_time / completed_tasks if completed_tasks > 0 else 0
            remaining_time = avg_time_per_task * (remaining_count - completed_tasks)

            # Calculate ETA
            eta = datetime.now() + timedelta(seconds=remaining_time)

            # Print progress
            print(f"\rProgress: {processed_count + completed_tasks}/{total_links} | "
                  f"Remaining: {remaining_count - completed_tasks} | "
                  f"Elapsed: {timedelta(seconds=int(elapsed_time))} | "
                  f"ETA: {eta.strftime('%H:%M:%S')}", end='', flush=True)

    print()  # New line after progress indicator

    # Update the original data with successful results
    for url, start_param in progress["processed"].items():
        # Find and replace the URL in the original data
        def replace_url_recursive(obj):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key == "url" and isinstance(value, str) and value == url:
                        obj[key] = start_param
                    elif isinstance(value, (dict, list)):
                        replace_url_recursive(value)
            elif isinstance(obj, list):
                for item in obj:
                    replace_url_recursive(item)

        replace_url_recursive(data)

    # Save the updated JSON data
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"\nProcessing complete. Output saved to {output_file}")
    print(f"Progress saved to {progress_file}")
    print(f"Successfully processed: {len(progress['processed'])} links")


def main():
    input_file = "rogd.json"
    num_workers = 50  # You can adjust this number as needed

    if not os.path.exists(input_file):
        print(f"Input file does not exist: {input_file}")
        sys.exit(1)

    # Using multiple workers for parallel processing
    process_json_file(input_file, num_workers)


if __name__ == "__main__":
    main()