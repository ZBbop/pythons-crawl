import requests
from bs4 import BeautifulSoup
from collections import deque
import xml.etree.ElementTree as ET
import csv
import os
import gzip
from io import BytesIO
import pandas as pd


initial_url = 'https://example.com'
root_domain = initial_url.split('/')[2]
scheme = initial_url.split(':')[0] + '://'
urls_to_crawl = set()
sitemap_contents = set()
urls_crawled = []
#data to output
crawl_overview_data = []
links_data = []

# File paths
urls_to_crawl_file = r'C:\full\file\path.csv'  # Update with actual file path
urls_crawled_file = r'C:\full\file\path.csv'  # Update with actual file path

# Function to read URLs from a CSV file, starting from the second row
def read_urls_from_csv(file_path, url_column_index=0):
    urls = []
    if os.path.exists(file_path):
        with open(file_path, 'r', newline='', encoding='utf-8') as file:
            reader = csv.reader(file)

            # Skip the first row (header)
            next(reader, None)  

            for row in reader:
                if row:  # Check if the row is not empty
                    urls.append(row[url_column_index].strip())  # Read URL from specified column index
    return urls

# Read URLs from CSV files
if urls_to_crawl_file:
    urls_to_crawl = set(read_urls_from_csv(urls_to_crawl_file))
if urls_crawled_file:
    urls_crawled = read_urls_from_csv(urls_crawled_file)

# parse the sitemap into locs
def parse_sitemap(url, urls_to_crawl, sitemap_contents):
    response = requests.get(url)
    if response.status_code != 200:
       return urls_to_crawl, sitemap_contents

    if 'Content-Type' in response.headers and response.headers['Content-Type'] == 'application/x-gzip':
       decompressed_data = gzip.GzipFile(fileobj=BytesIO(response.content)).read()
       soup = BeautifulSoup(decompressed_data, "xml")
    else:
       soup = BeautifulSoup(response.content.decode('utf-8'), "xml")
    urls = soup.findAll('loc')
    sitemaps = soup.findAll('sitemap')

    if not urls and not sitemaps:
        return urls_to_crawl, sitemap_contents

    for u in urls:
        url_str = u.string
        if '/wp-content/uploads/' not in url_str:
            if url_str not in urls_to_crawl and url_str not in urls_crawled:
                urls_to_crawl.add(url_str)
                sitemap_contents.add(url_str)

    if sitemaps:
        for u in sitemaps:
            sitemap_url = u.find('loc').string
            urls_to_crawl, sitemap_contents = parse_sitemap(sitemap_url, urls_to_crawl, sitemap_contents)

    return urls_to_crawl, sitemap_contents

# if the initial_url is a sitemap or if it is a page
if 'sitemap' in initial_url and 'xml' in initial_url:
    # Parse the XML sitemap and populate the urls_to_crawl array
    parse_sitemap(initial_url, urls_to_crawl, sitemap_contents)
else:
    # Strip out the root domain and add 'robots.txt'
    robots_url = scheme + root_domain + '/robots.txt'
    response = requests.get(robots_url)
    robots_txt = response.text.split('\n')

    # Look for lines that start with 'Sitemap: '. The rest of this line is an xml sitemap.
    sitemap_urls = [line.split(': ')[1] for line in robots_txt if line.startswith('Sitemap: ')]

    # Parse the locs from each sitemap found and append to urls_to_crawl
    for sitemap_url in sitemap_urls:
        urls = parse_sitemap(sitemap_url, urls_to_crawl, sitemap_contents)
        for url in urls:
            if 'sitemap' in url and 'xml' in url:
                parse_sitemap(url, urls_to_crawl, sitemap_contents)
            elif url not in urls_to_crawl and url not in urls_crawled:
                urls_to_crawl.add(url)
                sitemap_contents.add(url)

#url_status = "null"
# open empty array for possible redirect chains
destinations = []
# start count of redirects
redirects = 0

# get url status code
def get_url_status(url):
    global destinations, redirects
    try:
        # get the url
        status = requests.get(url)
        # store the status code
        url_status = status.status_code
        print(url_status)
        # if there are redirects
        if len(status.history) > 0:
            # get the trace history of the get request
            h = status.history
            # intialize counter, maybe not necessary
            i = 0
            # update redirects count to be the number of items in the history array
            redirects = len(status.history)
            # loop to create variables for export
            for resp in h:
                #add the redirect destination to the destinations array
                destinations.append(resp.headers['Location'])
        # if no redirects
        else:
            destinations.append("null")
    except requests.exceptions.MissingSchema:
        url_status = "Malformed URL"
    except requests.exceptions.ConnectionError:
        url_status = "Connection Problem"
    except requests.exceptions.Timeout:
        url_status = "Connection Timeout"
    except requests.exceptions.TooManyRedirects:
        url_status = "Redirect Loop or Too Many"
    except requests.exceptions.InvalidSchema:
        url_status = "Invalid Schema"
    return url_status

while urls_to_crawl:
    url = urls_to_crawl.pop()
    # Make the soup
    if scheme not in url:
        if root_domain not in url:
            url = f"{scheme}{root_domain}{url}"
        url = f"{scheme}{url}"
    url_status = get_url_status(url)
    if url_status == 200:
        #print(requests.get(url).headers)
        if 'sitemap' in url and 'xml' in url:
            parse_sitemap(url, urls_to_crawl, sitemap_contents)
            continue
        elif 'wp-content/' in url:
            continue
        elif 'Content-Type' in requests.get(url).headers and 'text/html' in requests.get(url).headers['Content-Type']:
            response = requests.get(url)
            soup = BeautifulSoup(response.content, 'html.parser')
            # Store the DOM in a variable
            dom = response.text
            # Check if in sitemap
            sitemap_bool = 0
            if url in sitemap_contents:
                sitemap_bool = 1
            else:
                sitemap_bool = 0

            print(url)    
            # Remove the URL from the urls_to_crawl array
            if url in urls_to_crawl:
                urls_to_crawl.remove(url)
            # Add it to the urls_crawled array
            urls_crawled.append(url)

            # get and check links
            out_links = 0
            in_links = 0
            redirect_links = 0
            links_404 = 0
            lnx = soup.find_all('a')
            links_on_page = len(lnx)
            link_href = []
            link_anchor = []
            link_url_status = 0
            for link in lnx:
                l = link.get('href')
                t = link.get_text().strip()
                if l.startswith('/') or l.startswith ('#'):
                    l = f"{scheme}{root_domain}{l}"
                if root_domain in l:
                    #if 'Content-Type' in requests.get(l).headers and 'text/html' in requests.get(l).headers['Content-Type']:
                    link_url_status = get_url_status(link)
                    if link_url_status == 301 or link_url_status == 302:
                        redirect_links += 1
                    elif link_url_status == 404:
                        links_404 += 1
                    elif link_url_status == 200 and l not in urls_to_crawl and l not in urls_crawled:
                        if '#' not in l:
                            if '/wp-content/' not in l:
                                urls_to_crawl.add(l)
                    in_links += 1
                    #else:
                    #    in_links += 1
                else:
                    out_links += 1
                
                if t and l:
                    link_dict = {
                        'url crawled': url,
                        'link_anchor': t,
                        'link_href': l,
                        'link_url_status': link_url_status
                    }
                    # links to array for export
                    links_data.append(link_dict)
            
            # parse the heading tags
            h1_raw = soup.find_all('h1')
            h1 = []
            h2_raw = soup.find_all('h2')
            h2 = []
            h3_raw = soup.find_all('h3')
            h3 = []

            # extract the strings and add to arrays
            for h in h1_raw:
                heading = str(h.string)
                h1.append(heading)
            for h in h2_raw:
                heading = str(h.string)
                h2.append(heading)
            for h in h3_raw:
                heading = str(h.string)
                h3.append(heading)

            # Extract page title
            if soup.title.string:
                page_title = str(soup.title.string)
            else:
                page_title = 'No Title'
            
            # Extract all meta tags
            meta_tags = soup.find_all('meta')
            meta_tag_names = []
            meta_content_names = []
            for meta in meta_tags:
                if not meta.get('name'):
                    continue
                else: 
                    meta_tag_names.append(meta.get('name'))
                    meta_content_names.append(meta.get('content'))

            #output to array
            crawl_overview_data.append({
                'url crawled': url,
                'url_status': url_status,
                'sitemap_bool': sitemap_bool,
                'out_links': out_links,
                'in_links': in_links,
                'redirect_links': redirects,
                'links_404': links_404,
                'page_title': page_title,
                'h1': h1,
                'h2': h2,
                'h3': h3
            })

            # Write crawl_overview_data and links_data to CSV files
            if crawl_overview_data:
                with open('vcl-crawl_overview.csv', 'a', newline='', encoding='utf-8') as file:
                    writer = csv.DictWriter(file, fieldnames=crawl_overview_data[0].keys())
                    if not os.path.isfile('vcl-crawl_overview.csv') or os.stat('vcl-crawl_overview.csv').st_size == 0:
                        writer.writeheader()
                    writer.writerows(crawl_overview_data)
            else:
                print("No data to write to CSV.")
        
            if links_data:
                with open('vcl-links.csv', 'a', newline='', encoding='utf-8') as file:
                    writer = csv.DictWriter(file, fieldnames=links_data[0].keys())
                    if not os.path.isfile('vcl-links.csv') or os.stat('vcl-links.csv').st_size == 0:
                        writer.writeheader()
                    writer.writerows(links_data)
            else:
                print("No data to write to CSV.")

            if urls_to_crawl:
                with open('vcl-urls_to_crawl.csv', 'a', newline='', encoding='utf-8') as file:
                    writer = csv.DictWriter(file, fieldnames=['URL'])
                    if not os.path.isfile('vcl-urls_to_crawl.csv') or os.stat('vcl-urls_to_crawl.csv').st_size == 0:
                        writer.writeheader()
                    for url in urls_to_crawl:
                        writer.writerow({'URL': url})
            else:
                print("No data to write to CSV.")

            # Clear crawl_overview_data and links_data for the next iteration
            crawl_overview_data.clear()
            links_data.clear()
            redirects = 0
            print(len(urls_to_crawl))
            print(len(urls_crawled))

    elif url_status > 200:
        # Remove the URL from the urls_to_crawl array
        if url in urls_to_crawl:
            urls_to_crawl.remove(url)
        # Add it to the urls_crawled array
        urls_crawled.append(url)
        # Add the strings to the urls_to_crawl array
        ### TODO ###
        # this needs to only take the final item from destinations
        #if destinations not in urls_to_crawl and destinations not in urls_crawled:
        #    urls_to_crawl.add(destinations)
        # if url in sitemap_contents:
        # Do things

# Run a link count between the crawl files
df_links = pd.read_csv('vcl-links.csv')
site_internal_links = df_links.iloc[:, 2]

df_overview = pd.read_csv('vcl-crawl_overview.csv')
urls_crawled = df_overview.iloc[:, 0]

site_internal_links = site_internal_links.str.lower().str.rstrip('/')
urls_crawled = urls_crawled.str.lower().str.rstrip('/')

# Create a dictionary to hold the counts of each URL
url_counts = {}
for url in urls_crawled:
    # Count how many times the URL appears in site_internal_links
    #count = site_internal_links.isin([url]).sum()
    count = site_internal_links.apply(lambda x: x == url).sum()
    url_counts[url] = count

#good to leave for verification of crawl in terminal without having to open the files
# a lot of zeroes means something went wrong
print(url_counts) 

# add count to crawl_overview
url_search = df_overview.iloc[:, 0]
df_overview['links_in'] = url_search.apply(lambda x: url_counts.get(x, 0))

# Save the updated dataframe back to the CSV file
df_overview.to_csv('vcl-crawl_overview.csv', index=False)
