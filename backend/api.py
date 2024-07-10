import os
import requests
import feedparser
import openai
import json
from dotenv import load_dotenv
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

# Load environment variables from .env file
load_dotenv()

# Set up OpenAI API key from environment variable
openai.api_key = os.getenv('OPENAI_API_KEY')
ieee_api_key = os.getenv('IEEE_API_KEY')

# Set up MongoDB connection
mongodb_uri = os.getenv('MONGODB_URI')
client = MongoClient(mongodb_uri, server_api=ServerApi('1'))
db = client["research_database"]
collection = db["articles"]

# Function to retrieve articles from Cornell Arxiv
def retrieve_cornell(max_results=50):
    # Construct the URL for querying Arxiv
    url_cornell = f"http://export.arxiv.org/api/query?search_query=all:molecule&max_results={max_results}"
    response_cornell = requests.get(url_cornell)
    
    # Check if the request was successful
    if response_cornell.status_code == 200:
        feed = feedparser.parse(response_cornell.content)
        
        # If no entries are found, return
        if not feed.entries:
            return

        # Process each entry in the feed
        for entry in feed.entries:
            article_data = {
                "source": "Cornell Arxiv",
                "url": entry.get('id', ''),
                "title": entry.get('title', 'No title available'),
                "content": entry.get('summary', 'No summary available')
            }
            process_article(article_data)

# Function to retrieve articles from Europe PMC
def retrieve_euro(page_size=50):
    url_euro = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    params = {
        "query": "molecule inhibitor dna",
        "format": "json",
        "pageSize": page_size
    }
    response_euro = requests.get(url_euro, params=params)
    
    # Check if the request was successful
    if response_euro.status_code == 200:
        data = response_euro.json()
        articles = data.get('resultList', {}).get('result', [])
        
        # If no articles are found, return
        if not articles:
            return
        
        # Process each article in the result
        for article in articles:
            content = article.get('abstractText', '')
            if not content:
                # If no abstract, concatenate available metadata
                content = (
                    f"Title: {article.get('title', 'No title available')}. "
                    f"Authors: {article.get('authorString', 'No authors available')}. "
                    f"Journal: {article.get('journalTitle', 'No journal available')} ({article.get('pubYear', 'No year available')})."
                )
            
            article_data = {
                "source": "Europe PMC",
                "doi": article.get('doi', 'NAN'),
                "title": article.get('title', 'No title available'),
                "content": content
            }
            process_article(article_data)

# Function to retrieve articles from IEEE Xplore
def retrieve_ieee(query, max_records=50):
    url = "http://ieeexploreapi.ieee.org/api/v1/search/articles"
    params = {
        "apikey": ieee_api_key,
        "format": "json",
        "max_records": max_records,
        "start_record": 1,
        "sort_order": "asc",
        "sort_field": "article_number",
        "querytext": query
    }
    
    response = requests.get(url, params=params)
    # Check if the request was successful
    if response.status_code == 200:
        articles = response.json().get('articles', [])
        
        # If no articles are found, return
        if not articles:
            return

        # Process each article in the result
        for article in articles:
            article_data = {
                "source": "IEEE Xplore",
                "title": article.get('title', 'No title available'),
                "content": article.get('abstract', 'No abstract available')
            }
            process_article(article_data)

# Function to process and store the article data
def process_article(article_data):
    content = article_data.get('content', '')
    if content == 'No summary available' or content == 'No abstract available':
        # If no content, provide default summary and topics
        summary = "As there's no available content provided, a summary cannot be created."
        topics = {
            "topic_1": "The main topics in the provided text are: lack of available content",
            "topic_2": "and inability to create a summary."
        }
    else:
        # Generate summary and extract topics using OpenAI
        summary = summarize_with_openai(content)
        topics = extract_topics_with_openai(summary)
    
    article_data.update({"summary": summary, "topics": topics})
    insert_to_mongodb(article_data)

# Function to generate summary using OpenAI's GPT-4
def summarize_with_openai(content):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": f"Please summarize the following content: {content}"}
            ],
            max_tokens=150
        )
        summary = response.choices[0].message['content'].strip()
        return summary
    except Exception as e:
        return "Summarization failed"

# Function to extract topics using OpenAI's GPT-4
def extract_topics_with_openai(text):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": f"Extract the main topics from the following text: {text}"}
            ],
            max_tokens=100
        )
        topics = response.choices[0].message['content'].strip().split(', ')
        return {f"topic_{i+1}": topic for i, topic in enumerate(topics)}
    except Exception as e:
        return {"error": "Topic extraction failed"}

# Function to insert article data into MongoDB
def insert_to_mongodb(article_data):
    try:
        collection.insert_one(article_data)
        print(f"Article '{article_data['title']}' inserted successfully!")
    except Exception as e:
        print(f"Error inserting article to MongoDB: {e}")

# Main script to retrieve articles from different sources
if __name__ == "__main__":
    retrieve_cornell(max_results=1)
    retrieve_euro(page_size=1)
    retrieve_ieee("molecule inhibitor dna", max_records=1)
