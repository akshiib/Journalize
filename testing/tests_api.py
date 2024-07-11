import unittest
from unittest.mock import patch, MagicMock, call
import sys
import os

# ensure the backend module can be found
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# mock environment variables
os.environ['OPENAI_API_KEY'] = 'test_openai_api_key'
os.environ['IEEE_API_KEY'] = 'test_ieee_api_key'
os.environ['TEXTRAZOR_API_KEY'] = 'test_textrazor_api_key'
os.environ['MONGODB_URI'] = 'test_mongodb_uri'

# import functions to be tested from backend.api
from backend.api import (
    retrieve_cornell,
    retrieve_euro,
    retrieve_ieee,
    summarize_with_openai,
    extract_topics_with_openai,
    insert_to_mongodb,
    process_article
)

class TestApi(unittest.TestCase):

    # mock the requests.get function used in retrieve_cornell
    @patch('backend.api.requests.get')
    def test_retrieve_cornell(self, mock_get):
        # setup the mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = '<feed><entry><id>test_id</id><title>Test Title</title><summary>Test Summary</summary></entry></feed>'
        mock_get.return_value = mock_response

        # mock the process_article function
        with patch('backend.api.process_article') as mock_process_article:
            retrieve_cornell(2, 'test_keywords')
            mock_process_article.assert_called_once()  # ensure process_article is called once
            article_data = mock_process_article.call_args[0][0]  # get the argument passed to process_article
            self.assertEqual(article_data['source'], 'Cornell Arxiv')  # check the source of the article
            self.assertEqual(article_data['title'], 'Test Title')  # check the title of the article
            self.assertEqual(article_data['content'], 'Test Summary')  # check the content of the article
            print("Test `test_retrieve_cornell`: PASSED")

    # mock the requests.get function used in retrieve_euro
    @patch('backend.api.requests.get')
    def test_retrieve_euro(self, mock_get):
        # setup the mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'resultList': {
                'result': [
                    {
                        'title': 'Test Title',
                        'abstractText': 'Test Abstract',
                        'doi': '10.1000/test',
                        'authorString': 'Test Author',
                        'journalTitle': 'Test Journal',
                        'pubYear': '2024'
                    }
                ]
            }
        }
        mock_get.return_value = mock_response

        # mock the process_article function
        with patch('backend.api.process_article') as mock_process_article:
            retrieve_euro(2, 'test_keywords')
            mock_process_article.assert_called_once()  # ensure process_article is called once
            article_data = mock_process_article.call_args[0][0]  # get the argument passed to process_article
            self.assertEqual(article_data['source'], 'Europe PMC')  # check the source of the article
            self.assertEqual(article_data['title'], 'Test Title')  # check the title of the article
            self.assertEqual(article_data['content'], 'Test Abstract')  # check the content of the article
            print("Test `test_retrieve_euro`: PASSED")

    # mock the requests.get function used in retrieve_ieee
    @patch('backend.api.requests.get')
    def test_retrieve_ieee(self, mock_get):
        # setup the mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'articles': [
                {
                    'title': 'Test Title',
                    'abstract': 'Test Abstract'
                }
            ]
        }
        mock_get.return_value = mock_response

        # mock the process_article function
        with patch('backend.api.process_article') as mock_process_article:
            retrieve_ieee(2, 'test_keywords')
            mock_process_article.assert_called_once()  # ensure process_article is called once
            article_data = mock_process_article.call_args[0][0]  # get the argument passed to process_article
            self.assertEqual(article_data['source'], 'IEEE Xplore')  # check the source of the article
            self.assertEqual(article_data['title'], 'Test Title')  # check the title of the article
            self.assertEqual(article_data['content'], 'Test Abstract')  # check the content of the article
            print("Test `test_retrieve_ieee`: PASSED")

    # mock the openai.ChatCompletion.create function used in summarize_with_openai
    @patch('backend.api.openai.ChatCompletion.create')
    def test_summarize_with_openai(self, mock_openai_create):
        # setup the mock response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message={'content': 'Test Summary'})]
        mock_openai_create.return_value = mock_response

        summary = summarize_with_openai("Test content")
        self.assertEqual(summary, 'Test Summary')  # check the summary returned
        print("Test `test_summarize_with_openai`: PASSED")

    # mock the openai.ChatCompletion.create function used in extract_topics_with_openai
    @patch('backend.api.openai.ChatCompletion.create')
    def test_extract_topics_with_openai(self, mock_openai_create):
        # setup the mock response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message={'content': 'Topic1, Topic2'})]
        mock_openai_create.return_value = mock_response

        topics = extract_topics_with_openai("Test text")
        self.assertEqual(topics, {"topic_1": "Topic1", "topic_2": "Topic2"})  # check the topics returned
        print("Test `test_extract_topics_with_openai`: PASSED")

    # mock the MongoDB collection object
    @patch('backend.api.collection')
    def test_insert_to_mongodb(self, mock_collection):
        article_data = {
            "source": "Test Source",
            "title": "Test Title",
            "content": "Test Content"
        }
        insert_to_mongodb(article_data)
        mock_collection.insert_one.assert_called_once_with(article_data)  # ensure insert_one is called once with correct data
        print("Test `test_insert_to_mongodb`: PASSED")

    # mock the insert_to_mongodb function used in process_article
    @patch('backend.api.insert_to_mongodb')
    def test_process_article_with_no_content(self, mock_insert_to_mongodb):
        article_data = {
            "source": "Test Source",
            "title": "Test Title",
            "content": "No summary available"
        }
        process_article(article_data)
        self.assertEqual(article_data['summary'], "As there's no available content provided, a summary cannot be created.")  # check the summary
        self.assertIn("topic_1", article_data['topics'])  # check the topics
        self.assertIn("topic_2", article_data['topics'])
        mock_insert_to_mongodb.assert_called_once_with(article_data)  # ensure insert_to_mongodb is called once with correct data
        print("Test `test_process_article_with_no_content`: PASSED")

    # mock the summarize_with_openai, extract_topics_with_openai, and insert_to_mongodb functions used in process_article
    @patch('backend.api.summarize_with_openai')
    @patch('backend.api.extract_topics_with_openai')
    @patch('backend.api.insert_to_mongodb')
    def test_process_article_with_content(self, mock_insert_to_mongodb, mock_extract_topics, mock_summarize):
        mock_summarize.return_value = "Test Summary"
        mock_extract_topics.return_value = {"topic_1": "Topic1", "topic_2": "Topic2"}

        article_data = {
            "source": "Test Source",
            "title": "Test Title",
            "content": "This is a test content."
        }
        process_article(article_data)
        self.assertEqual(article_data['summary'], "Test Summary")  # check the summary
        self.assertEqual(article_data['topics'], {"topic_1": "Topic1", "topic_2": "Topic2"})  # check the topics
        mock_insert_to_mongodb.assert_called_once_with(article_data)  # ensure insert_to_mongodb is called once with correct data
        print("Test `test_process_article_with_content`: PASSED")

# run the tests
if __name__ == '__main__':
    unittest.main()