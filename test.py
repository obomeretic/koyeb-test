#!/usr/bin/env python3
"""
Combined script that uses vcloud_resolver.sh logic to get to hubcloud.one/tg/go.php?re=... URL
and then uses debug_new_url.py logic to follow the redirect chain and extract the start parameter
"""

import sys
import httpx
import re
import base64
from urllib.parse import urlparse, parse_qs, unquote_plus


def get_hubcloud_url_from_vcloud(vcloud_url):
    """
    Replicate the functionality of vcloud_resolver.sh to get to the hubcloud URL with re parameter
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

    print(f"Processing vcloud URL: {vcloud_url}")

    # Create a fresh client for the first phase
    with httpx.Client() as client:
        # Step 1: GET the vcloud link to get the HTML
        print("Step 1: Fetching HTML from vcloud URL...")
        response = client.get(vcloud_url, headers=headers)
        html_response = response.text
        print(f"Status code: {response.status_code}")

        # Step 2: Extract the cdn.ampproject.org URL from the HTML
        print("Step 2: Extracting cdn.ampproject.org URL...")
        amp_url_match = re.search(r'https://[^\s"<>\']*\.cdn\.ampproject\.org[^\s"<>\']*', html_response)
        
        if not amp_url_match:
            print("Looking for any ampproject.org URLs...")
            all_amp_urls = re.findall(r'https://[^\s"<>\']*ampproject[^\s"<>\']*', html_response)
            print(f"Found potential ampproject URLs: {all_amp_urls[:5]}")
            if all_amp_urls:
                amp_url = all_amp_urls[0]  # Use the first one found
                print(f"Using first ampproject URL: {amp_url}")
            else:
                raise ValueError("Could not find cdn.ampproject.org URL in the response")
        else:
            amp_url = amp_url_match.group(0)

        print(f"Found AMP URL: {amp_url}")

        # Step 3: Decode the base64 string after /foo/ to get the URL with id parameter
        print("Step 3: Extracting and decoding base64 string after /foo/...")
        foo_match = re.search(r'foo/([^/]*)', amp_url)

        if not foo_match:
            raise ValueError("Could not extract base64 string after /foo/")

        base64_part = foo_match.group(1)
        try:
            decoded_bytes = base64.b64decode(base64_part)
            decoded_url = decoded_bytes.decode('utf-8')
        except Exception as e:
            raise ValueError(f"Could not decode base64 string: {str(e)}")

        print(f"Decoded URL: {decoded_url}")

        # Step 4: Extract the id parameter from the decoded URL
        print("Step 4: Extracting id parameter...")
        # Extract id parameter directly from the URL string to preserve + signs
        id_match = re.search(r'[?&]id=([^&]*)', decoded_url)
        if not id_match:
            raise ValueError("Could not extract id parameter from decoded URL")

        id_value = id_match.group(1)
        print(f"ID parameter: {id_value}")

        # Step 5: Construct the hubcloud.one/tg//go?id= URL and GET it
        print("Step 5: Constructing and requesting hubcloud URL with id parameter...")
        hubcloud_url = f"https://hubcloud.one/tg//go?id={id_value}"
        print(f"Requesting: {hubcloud_url}")

        # Perform the request with follow_redirects=True to get the final URL like the bash script does
        final_response = client.get(hubcloud_url, headers=headers, follow_redirects=True)
        final_url = str(final_response.url)
        print(f"Received redirect URL: {final_url}")

        # Step 6: Decode the base64 string after /re2/ in the response
        print("Step 6: Extracting and decoding base64 string after /re2/...")
        re2_match = re.search(r're2/([^/]+)', final_url)

        if not re2_match:
            raise ValueError("Could not extract base64 string after /re2/")

        base64_re2 = re2_match.group(1)
        # URL decode the base64 string to restore + signs
        base64_re2 = unquote_plus(base64_re2)
        try:
            decoded_re2_bytes = base64.b64decode(base64_re2)
            decoded_re2 = decoded_re2_bytes.decode('utf-8')
        except Exception as e:
            raise ValueError(f"Could not decode base64 string after /re2/: {str(e)}")

        print(f"Decoded URL after re2/: {decoded_re2}")

        # Step 7: Decode the base64 string in the r parameter of the resulting URL
        print("Step 7: Extracting and decoding base64 string from r parameter...")
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

        print(f"Decoded URL from r parameter: {decoded_r}")

        return decoded_r


def follow_redirect_chain_and_extract_start(decoded_r_url):
    """
    Follow the redirect chain from the decoded_r URL and extract the start parameter
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

    print("\n--- Following redirect chain from decoded_r URL ---")

    current_url = decoded_r_url
    max_redirects = 10
    redirect_count = 0

    print(f"Starting with URL: {current_url}")

    # Create a fresh client for the second phase to avoid session persistence
    with httpx.Client() as client:
        while redirect_count < max_redirects:
            print(f"Making request {redirect_count + 1} to: {current_url}")
            response = client.get(current_url, headers=headers, follow_redirects=False)
            location = response.headers.get('Location')

            print(f"Response status: {response.status_code}")
            print(f"Location header: {location}")
            print(f"Has location: {bool(location)}")

            if location:
                print(f"Redirect {redirect_count + 1}: {current_url} -> {location}")
                current_url = location
                redirect_count += 1
                continue  # Continue the loop to follow the next redirect

            # Check for meta refresh in HTML content
            meta_refresh_match = re.search(r'url=([^\'"&\s<>]+)', response.text)
            print(f"Meta refresh match: {meta_refresh_match}")

            if meta_refresh_match:
                import urllib.parse
                meta_url = urllib.parse.unquote(meta_refresh_match.group(1))
                # If the URL is relative, make it absolute
                if not meta_url.startswith(('http://', 'https://')):
                    base_url = str(response.url)
                    parsed_base = urlparse(base_url)
                    meta_url = f"{parsed_base.scheme}://{parsed_base.netloc}{meta_url}"

                print(f"Meta refresh redirect {redirect_count + 1}: {current_url} -> {meta_url}")
                current_url = meta_url
                redirect_count += 1
                continue  # Continue the loop to follow the next redirect

            # No more redirects
            print("No more redirects found")
            final_response_php = response
            final_redirect_url = str(response.url)
            break
        else:
            # If we hit the max redirects limit
            print("Hit max redirects limit")
            final_response_php = response
            final_redirect_url = str(response.url)

        print(f"Final redirect URL: {final_redirect_url}")

        # Extract from the final redirect URL after all redirects
        final_parsed = urlparse(final_redirect_url)
        final_query = parse_qs(final_parsed.query)
        start_param_list = final_query.get('start', [])
        print(f"Start parameters found: {start_param_list}")
        
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


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <vcloud_url>")
        sys.exit(1)
    
    vcloud_url = sys.argv[1]
    
    try:
        # Step 1: Use vcloud_resolver.sh logic to get to the hubcloud URL
        decoded_r_url = get_hubcloud_url_from_vcloud(vcloud_url)

        # Add a delay between the two phases to improve success rate
        print("\n--- Waiting 1 second before following redirect chain ---")
        import time
        time.sleep(3)

        # Step 2: Use debug_new_url.py logic to follow the redirect chain and extract start parameter
        start_param = follow_redirect_chain_and_extract_start(decoded_r_url)
        
        print(f"\n=== RESULT ===")
        print(start_param)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()