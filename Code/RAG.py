from __future__ import print_function
import logging
import os
import pandas as pd
import glob
from dotenv import load_dotenv
import logging
from llama_index.embeddings.azure_openai import AzureOpenAIEmbedding
from llama_index.llms.azure_openai import AzureOpenAI
from llama_index.core import ( Settings, VectorStoreIndex, SimpleDirectoryReader)
from llama_index.core.callbacks import CallbackManager, LlamaDebugHandler
from llama_index.core import (StorageContext, ServiceContext)
import numpy as np
from sqlalchemy import *
from llama_index.core import SQLDatabase, Document
from llama_index.core.indices.struct_store import SQLTableRetrieverQueryEngine
from llama_index.core.retrievers import VectorIndexAutoRetriever
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.vector_stores.duckdb import DuckDBVectorStore
from llama_index.core.retrievers import VectorIndexAutoRetriever
from llama_index.core.vector_stores import MetadataInfo, VectorStoreInfo
from langchain.text_splitter import RecursiveCharacterTextSplitter
from llama_index.core.node_parser import LangchainNodeParser
from sqlalchemy import (create_engine,MetaData,Table,Column,String,Integer,select,column,)
from sqlalchemy.dialects.postgresql import (INTEGER, FLOAT, BIGINT, VARCHAR, DOUBLE_PRECISION)
from llama_index.core.indices.struct_store import SQLTableRetrieverQueryEngine
from llama_index.core.objects import (SQLTableNodeMapping,ObjectIndex,SQLTableSchema,)
from llama_index.core import VectorStoreIndex

logging.getLogger().setLevel(logging.ERROR)

llama_debug = LlamaDebugHandler(print_trace_on_end=True)
callback_manager = CallbackManager([llama_debug])

Settings.callback_manager = callback_manager

load_dotenv('/Credentials/.env')

#Azure OpenAI Creds
endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
credential = os.getenv("AZURE_OPENAI_API_KEY")
azure_openai_api_version = "2024-04-01-preview"
azure_openai_embedding_deployment = "text-embedding-ada-002"
embedding_model_name = "text-embedding-ada-002"
llm_model_name = "gpt-35-turbo-16k"
api_type = "azure"

llm = AzureOpenAI(
            model = llm_model_name,
            deployment_name = llm_model_name,
            api_key = credential,
            azure_endpoint = endpoint,
            api_version = azure_openai_api_version,
            api_type = api_type
        )

embed_model = AzureOpenAIEmbedding(
            model = embedding_model_name,
            deployment_name = embedding_model_name,
            api_key = credential,
            azure_endpoint = endpoint,
            api_version = azure_openai_api_version,
            api_type = api_type,
            embed_batch_size=50
        )

Settings.llm = llm
Settings.embed_model = embed_model   

    
def create_sql_engine():
    engine = create_engine("duckdb:////Data/meded_ai_dev.duckdb", future=True)

    metadata_obj = MetaData()

    alter_schema = Table('graded_quizzes', 
                metadata_obj, 
                Column("quiz_id", INTEGER), 
                Column('quiz_type', VARCHAR), 
                Column('quiz_title', VARCHAR),
                Column('history_id', BIGINT),
                Column('submission_id', BIGINT),
                Column('student_score', DOUBLE_PRECISION),
                Column('quiz_question_count', BIGINT),
                Column('quiz_points_possible', DOUBLE_PRECISION),
                Column('question_points_possible', DOUBLE_PRECISION),
                Column('answer_points_scored', DOUBLE_PRECISION),
                Column('attempt', BIGINT),
                Column('question_name',VARCHAR),
                Column('question_type', VARCHAR),
                Column('question_text', VARCHAR),
                Column('question_answer', VARCHAR),
                Column('student_answer', VARCHAR),
                Column('course_id', VARCHAR),
                Column('accuracy', INTEGER),
                Column('completeness', INTEGER),
                autoload_with=engine, 
                extend_existing=True)
    
    with engine.connect() as connection:
        with connection:
            metadata=MetaData()
            my_table=Table("graded_quizzes", metadata, autoload_with=connection)
    
    sql_database = SQLDatabase(engine, include_tables=["graded_quizzes"])

    table_node_mapping = SQLTableNodeMapping(sql_database)

    table_schema = [SQLTableSchema(table_name='graded_quizzes')]

    obj_index = ObjectIndex.from_objects(
        table_schema,
        table_node_mapping,
        VectorStoreIndex,
    )

    sql_query_engine = SQLTableRetrieverQueryEngine(
        sql_database,
        obj_index.as_retriever(similarity_top_k=1),
    )
    
    return(sql_query_engine)

def create_query_engine():
    logging.getLogger().setLevel(logging.WARNING)
    pd.set_option('future.no_silent_downcasting', True)
    # embed that content, with metadata for where they came from/what consolidation exercise they're a part of 

    reader = SimpleDirectoryReader("/Data/studentguides/", recursive=True, filename_as_id=True, required_exts=[".pdf", ".docx", ".xlsx", ".pptx"])

    documents = []
    for docs in reader.iter_data():
        file_filename = [x for x in glob.glob("/Data/coursedata_*/course_file.json",recursive=True) if docs[0].metadata['file_name'][0:6] in x][0]
        file_df = pd.read_json(file_filename)
        file_metadata = file_df.loc[file_df['filename'] == docs[0].metadata['file_name'][7:].replace('_','+')]
        if file_metadata.empty != True:                
            file_metadata = file_metadata.squeeze().to_dict()
            file_metadata = pd.DataFrame(file_metadata, index=[0]).replace(np.NaN, 0).replace(0, None)
            file_metadata = file_metadata.to_dict('records')[0]
            folder = file_metadata.get('folder_id')
        else:
            file_metadata = {}
            folder = ''

        folder_filename = [x for x in glob.glob("/Data/coursedata_*/course_folder.json",recursive=True) if docs[0].metadata['file_name'][0:6] in x][0]
        folder_df = pd.read_json(folder_filename)
        folder_metadata = folder_df.loc[folder_df['id'] == folder]
        if folder_metadata.empty != True:
            folder_metadata = folder_metadata.squeeze().to_dict()
            folder_metadata = pd.DataFrame(folder_metadata, index=[0]).replace(np.NaN, 0).replace(0, None)
            folder_metadata = folder_metadata.to_dict('records')[0]
            if 'Week' in folder_metadata['full_name']:
                week = [i for i in folder_metadata['full_name'].split("/") if 'Week' in i][0].replace('Week','').replace(' ','')
                folder_metadata.update({"week":week})
            full_name = folder_metadata['full_name'].split("/")[-1]
            folder_metadata.update({"folder_name":full_name})
        else:
            folder_metadata = {}
        
        course_filename = [x for x in glob.glob("/Data/coursedata_*/course_course.json",recursive=True) if docs[0].metadata['file_name'][0:6] in x][0]
        course_df = pd.read_json(course_filename)        
        course_metadata = course_df.loc[course_df['id'] == folder_metadata.get('context_id')]
        if course_metadata.empty != True:
            course_metadata = course_metadata.squeeze().to_dict()
            course_id = folder_metadata.get('context_id')
        else:
            course_metadata = {}
                
        for doc in docs:
            doc.metadata.update({"file_id": file_metadata.get('id'), "folder_id":file_metadata.get('folder_id'), "display_name":file_metadata.get('display_name')})
            doc.metadata.update({"week": folder_metadata.get('week'),  "folder_name": folder_metadata.get('folder_name')})
            doc.metadata.update({"course_id": course_metadata.get('id'), "course_name":course_metadata.get('name'),"course_code":course_metadata.get('course_code'),"course_term":course_metadata.get('term', {}).get('name')}) 
        documents.extend(docs)

    parser = LangchainNodeParser(RecursiveCharacterTextSplitter(
        # Set a really small chunk size, just to show.
        chunk_size=8000,
        chunk_overlap=20,
        length_function=len,
        is_separator_regex=False,
    ))

    nodes = parser.get_nodes_from_documents(documents)

    vector_store = DuckDBVectorStore(nodes=nodes)

    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    vector_index = VectorStoreIndex.from_documents(
        documents, storage_context=storage_context, embed_model=embed_model, llm=llm
    )
    
    vector_store_info = VectorStoreInfo(
    content_info="Student guides to help prepare for consolidation assessments",
    metadata_info=[
                MetadataInfo(
                    name="page_label",
                    description="What page of the file the context is from",
                    type="string",
                ),
                MetadataInfo(
                    name="file_name",
                    description="The name of the file the context is from",
                    type="string",
                ),
                MetadataInfo(
                    name="file_path",
                    description="The file path of the context file",
                    type="string",
                ),
                MetadataInfo(
                    name="file_type",
                    description="The type of file",
                    type="string",
                ),
                MetadataInfo(
                    name="file_size",
                    description="The size of the file in bytes",
                    type="integer",
                ),
                MetadataInfo(
                    name="creation_date",
                    description="When the file was created",
                    type="string",
                ),
                MetadataInfo(
                    name="last_modified_date",
                    description="When the file was last modified",
                    type="string",
                ),
                MetadataInfo(
                    name="display_name",
                    description="The name of the file",
                    type="string",
                ),
                MetadataInfo(
                    name="week",
                    description="The week the context was administered",
                    type="string",
                ),
                MetadataInfo(
                    name="folder_name",
                    description="The course folder that contains the file",
                    type="string",
                ),
                MetadataInfo(
                    name="course_id",
                    description="The unique identifier of the course",
                    type="integer",
                ),
                MetadataInfo(
                    name="course_name",
                    description="The full name of the course",
                    type="string",
                ),
                MetadataInfo(
                    name="course_code",
                    description="The shortened name of the course",
                    type="string",
                ),
                MetadataInfo(
                    name="course_term",
                    description="What term the course was offered in",
                    type="string",
                ),],)

    vector_auto_retriever = VectorIndexAutoRetriever(
        vector_index, vector_store_info=vector_store_info
    )

    retriever_query_engine = RetrieverQueryEngine.from_args(
        vector_auto_retriever, llm=llm
    )
    
    return(retriever_query_engine)