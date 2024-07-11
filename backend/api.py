import os
import requests
import feedparser
import openai
import json
from dotenv import load_dotenv
from pymongo import MongoClient, errors
from pymongo.server_api import ServerApi
import textrazor

# Load environment variables from .env file
load_dotenv()

# Set up OpenAI API key from environment variable
openai.api_key = os.getenv('OPENAI_API_KEY')
ieee_api_key = os.getenv('IEEE_API_KEY')
textrazor.api_key = os.getenv('TEXTRAZOR_API_KEY')

# Set up MongoDB connection
mongodb_uri = os.getenv('MONGODB_URI')
client = MongoClient(mongodb_uri, server_api=ServerApi('1'))
db = client["research_database"]
collection = db["articles"]

def user_input():
    user_inp = input("Enter your research question")
    keywords = ""
    client = textrazor.TextRazor(extractors=["entities"])
    response = client.analyze(user_inp)
    
    for entity in response.entities():
        keywords+=f"{(entity.english_id)} "
    
    words = keywords.split()
    seen = set()
    for word in words:
        word_l = word.lower()
        seen.add(word_l)
    
    # Join the unique words with commas
    result = '%20'.join(seen)
    return result

KEYWORDS = ""

# Function to retrieve articles from Cornell Arxiv
def retrieve_cornell(max_results=2):
    # Construct the URL for querying Arxiv
    url_cornell = f"http://export.arxiv.org/api/query?search_query=all:{KEYWORDS}&max_results={max_results}"
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
            print(article_data)
            process_article(article_data)

# Function to retrieve articles from Europe PMC
def retrieve_euro(page_size=50):
    url_euro = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    params = {
        "query": KEYWORDS,
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
def retrieve_ieee(max_records=50):
    url = "http://ieeexploreapi.ieee.org/api/v1/search/articles"
    params = {
        "apikey": ieee_api_key,
        "format": "json",
        "max_records": max_records,
        "start_record": 1,
        "sort_order": "asc",
        "sort_field": "article_number",
        "querytext": KEYWORDS
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

# Function to get articles from inside MongoDB
def get_articles():
    try: 
        articles = list(collection.find())
        return articles
    except errors.PyMongoError as e:
        print(f"Error retrieving articles from MongoDB: {e}")
        return []

# Define a function to retrieve articles based on given keywords
def retrieve_all(keywords):
    global KEYWORDS  # Make the KEYWORDS variable global to be accessible outside this function
    KEYWORDS = keywords 

    # Initialize an empty list to store articles
    articles = []

    # Function to collect articles from different sources
    def collect_articles(func, *args, **kwargs):
        nonlocal articles  # Access the 'articles' variable defined in the outer function
        func(*args, **kwargs)  # Call the provided function with arguments and keyword arguments
        # Ensure the 'process_article' function collects results into the 'articles' list
        # The 'process_article' function should be defined elsewhere in your code to append results

    # Collect articles from different sources with specified parameters
    collect_articles(retrieve_cornell, max_results=2)  # Retrieve 2 articles from Cornell
    collect_articles(retrieve_euro, page_size=2)      # Retrieve 2 articles from Euro
    collect_articles(retrieve_ieee, max_records=2)    # Retrieve 2 articles from IEEE

    return articles  # Return the list of collected articles

# Define a function to format raw article results
def format_results(raw_results):
    formatted_results = []  # Initialize an empty list to store formatted results

    # Loop through each raw result
    for result in raw_results:
        formatted_result = {
            'title': result.get('title', 'No title available'),  # Get the title or default if not present
            'source': result.get('source', 'Unknown source'),    # Get the source or default if not present
            'url': result.get('url', '#'),                       # Get the URL or default if not present
            'summary': result.get('summary', 'No summary available'),  # Get the summary or default if not present
            'content': result.get('content', 'No content available'),  # Get the content or default if not present
            'topics': []  # Initialize an empty list for topics
        }

        # Get topics from the result, default to an empty dictionary if not present
        topics = result.get('topics', {})
        for i in range(1, 3):  # Iterate to get up to two topics
            topic_key = f'topic_{i}'  # Construct the topic key (e.g., 'topic_1', 'topic_2')
            if topic_key in topics:  # Check if the topic exists in the result
                formatted_result['topics'].append(topics[topic_key])  # Add the topic to the list

        formatted_results.append(formatted_result)  # Add the formatted result to the list

    return formatted_results  # Return the list of formatted results


def gpt_output(user_input):
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": """You are a researcher explaining research papers based on questions asked to you"""},
            {"role": "user", "content": f"""Answer the following question in a few sentences: {user_input}
            """}
        ]
    )
    output = (completion.choices[0].message.content)
    return output

def chat():
    print("Welcome to the OpenAI Chatbot. Type 'quit' to exit.")
    while True:
        user_input = input("You: ")
        if user_input.lower() == "quit":
            break
        response = gpt_output(user_input)
        print(f"Chatbot: {response}")


# Main script to retrieve articles from different sources
# if __name__ == "__main__":
#     #retrieve_all()

