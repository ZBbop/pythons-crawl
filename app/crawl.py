import requests
from bs4 import BeautifulSoup
from collections import deque
import xml.etree.ElementTree as ET


initial_url = 'https://govclab.com/2023/05/30/the-venture-institute-the-vc-career-launchpad/'
root_domain = initial_url.split('/')[2]
scheme = initial_url.split(':')[0] + '://'
urls_to_crawl = []
sitemap_urls = []
urls_crawled = []

def parse_sitemap(sitemap_url):
  response = requests.get(sitemap_url)
  root = ET.fromstring(response.content)
  urls = [elem.text for elem in root.iter('loc')]
  return urls


if 'sitemap' in initial_url and 'xml' in initial_url:
  # Parse the XML sitemap and populate the urls_to_crawl array
  urls_to_crawl = deque(parse_sitemap(initial_url))
  sitemap_urls = deque(parse_sitemap(initial_url))
else:
  # Strip out the root domain and add 'robots.txt'
  robots_url = root_domain + '/robots.txt'
  response = requests.get(robots_url)
  robots_txt = response.text.split('\n')

  # Look for lines that start with 'Sitemap: '. The rest of this line is an xml sitemap.
  sitemap_urls = [line.split(': ')[1] for line in robots_txt if line.startswith('Sitemap: ')]

  # Parse the locs from each sitemap found and append to urls_to_crawl
  for sitemap_url in sitemap_urls:
    urls = [parse_sitemap(sitemap_url)]
    for url in urls:
      if 'sitemap' in url and 'xml' in url:
        urls_to_crawl.extend(parse_sitemap(url))
      else:
        urls_to_crawl.append(urls)

url_status = "null"
# open empty array for possible redirect chains
destinations = []
# start count of redirects
redirects = 0

# get url status code
def get_url_status(url):
    global url_status, destinations, redirects
    try:
        # get the url
        status = requests.get(url)
        # store the status code
        url_status = status.status_code
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

while urls_to_crawl:
    url = urls_to_crawl.pop()
    # Make the soup
    get_url_status(url)
    if 200 in url_status:
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        # Store the DOM in a variable
        dom = response.text
        # Check if in sitemap
        sitemap_bool = 0
        if url in sitemap_urls:
            sitemap_bool = 1
        else:
            continue
            
        # Remove the URL from the urls_to_crawl array
        urls_to_crawl.remove(url)
        # Add it to the urls_crawled array
        urls_crawled.append(url)

        # get and check links
        out_links = 0
        in_links = 0
        lnx = soup.find_all('a')
        links_on_page = len(lnx)
        link_href = []
        link_anchor = []
        for link in lnx:
            l = link.get('href')
            t = link.get_text()
            if t:
                link_anchor.append(t)
            if l:
                link_href.append(l)
                if l.startswith('/'):
                    l = f"{scheme}{root_domain}{l}"
                if root_domain in l:
                    if l not in urls_to_crawl:
                        urls_to_crawl.append(l)
                    in_links += 1
                else:
                    out_links += 1

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
        page_title = str(soup.title.string)
        
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


    elif 301 in url_status or 302 in url_status or 307 in url_status or 404 in url_status or 403 in url_status:
        # Remove the URL from the urls_to_crawl array
        urls_to_crawl.remove(url)
        # Add it to the urls_crawled array
        urls_crawled.append(url)
        urls_to_crawl.append(destinations)
