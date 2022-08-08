from dotenv import dotenv_values  # type: ignore
from data_parser import parse_comment_data
import logging
import vk  # type: ignore
import pymongo

config = dotenv_values(".env")
logging.basicConfig(
    filename='log/data_parsing.log',
    encoding='utf-8',
    level=getattr(logging, config['LOG_LEVEL'].upper())
)
api = vk.API(access_token=config['VK_API_TOKEN'])
db_client = pymongo.MongoClient(f"mongodb+srv://"
                                f"lerastromtsova:{config['MONGO_DB_PASSWORD']}"
                                f"@cluster0.ubfnhtk.mongodb.net/"
                                f"?retryWrites=true&w=majority")

if __name__ == '__main__':
    parse_comment_data(api)
