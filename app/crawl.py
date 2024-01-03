import requests
from bs4 import BeautifulSoup
from collections import deque
import xml.etree.ElementTree as ET
import os


initial_url = 'https://www.example.com'
root_domain = initial_url.split('/')[2]
scheme = initial_url.split(':')[0] + '://'
urls_to_crawl = []
sitemap_contents = []
urls_crawled = []
#data to output
crawl_overview_data = []
links_data = []

# parse the sitemap into locs
def parse_sitemap(url, urls_to_crawl, sitemap_contents):
 response = requests.get(url)
 if response.status_code != 200:
   return urls_to_crawl, sitemap_contents

 soup = BeautifulSoup(response.content, "xml")
 urls = soup.findAll('loc')
 sitemaps = soup.findAll('sitemap')

 if not urls and not sitemaps:
   return urls_to_crawl, sitemap_contents

 for u in urls:
  url_str = u.string
  if '/wp-content/uploads/' not in url_str:
    urls_to_crawl.append(url_str)
    sitemap_contents.append(url_str)

 if sitemaps:
   for u in sitemaps:
     sitemap_url = u.find('loc').string
     parse_sitemap(sitemap_url, urls_to_crawl, sitemap_contents)

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
  if url_status == 200:
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    # Store the DOM in a variable
    dom = response.text
    # Check if in sitemap
    sitemap_bool = 0
    if url in sitemap_contents:
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
    redirect_links = 0
    links_404 = 0
    lnx = soup.find_all('a')
    links_on_page = len(lnx)
    link_href = []
    link_anchor = []
    for link in lnx:
      l = link.get('href')
      t = link.get_text()
      get_url_status(link)
      if url_status == 301 or url_status == 302:
        redirect_links += 1
      elif url_status == 404:
        links_404 += 1
      if t:
          link_anchor.append(t)
      if l:
        link_href.append(l)
        if l.startswith('/'):
            l = f"{scheme}{root_domain}{l}"
        if root_domain in l:
          if l not in urls_to_crawl:
              if '#' not in l:
                urls_to_crawl.append(l)
          in_links += 1
        else:
          out_links += 1
          
    # links to array for export
    for href in link_href:
      links_data.append({
        'url crawled': url,
        'link_anchor': link_anchor,
        'link_href': href,
        'link_url_status': link_url_status
      })
      
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
    with open('crawl_overview.csv', 'a', newline='') as file:
     writer = csv.DictWriter(file, fieldnames=crawl_overview_data[0].keys())
     if not os.path.isfile('crawl_overview.csv') or os.stat('crawl_overview.csv').st_size == 0:
       writer.writeheader()
     writer.writerows(crawl_overview_data)
  
    with open('links.csv', 'a', newline='') as file:
      writer = csv.DictWriter(file, fieldnames=links_data[0].keys())
      if not os.path.isfile('links.csv') or os.stat('links.csv').st_size == 0:
        writer.writeheader()
      writer.writerows(links_data)

    # Clear crawl_overview_data and links_data for the next iteration
    crawl_overview_data.clear()
    links_data.clear()


  elif url_status > 200:
    # Remove the URL from the urls_to_crawl array
    urls_to_crawl.remove(url)
    # Add it to the urls_crawled array
    urls_crawled.append(url)
    # Add the strings to the urls_to_crawl array
    ### TODO ###
    # this needs to only take the final item from destinations
    urls_to_crawl.append(destinations)
    if url in sitemap_contents:
      # Do things
