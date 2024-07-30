from __future__ import print_function
import pandas as pd
from openai import AzureOpenAI
import json
import requests
import pandas as pd
from llama_index.llms.azure_openai import AzureOpenAI as AzureOAI
import re
import plotly.graph_objects as go
from sklearn.linear_model import LinearRegression

def get_courses(api_key):
    url = "https://canvas.harvard.edu/api/v1/courses"
    headers = {"Authorization": f"Bearer {api_key}"}
    courses = []
    courses_dict={}
    page = 1
    while True:
        params = {"page": page}
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()  # Raise an exception for 4xx/5xx status codes
            courses_page = json.loads(response.text)  # Convert response text to dictionary using json.loads()
            for course in courses_page:
                courses_dict[str(course['id'])] = course['name']
            if "next" not in response.links:
                break  # No more pages to fetch
            page += 1
        except requests.exceptions.RequestException as e:
            print(f"Error fetching courses")
    return courses_dict

def get_quizzes(api_key, course):
    quizzes = []
    quiz_dict = {}
    quiz_dict[str(course)] = {}
    url = f"https://canvas.harvard.edu/api/v1/courses/{course}/quizzes"
    headers = {"Authorization": f"Bearer {api_key}"}
    page = 1
    while True:
        params = {"page": page, "per_page":"100"}
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()  # Raise an exception for 4xx/5xx status codes
            quizzes_page = json.loads(response.text)  # Convert response text to dictionary using json.loads()
            for quiz in quizzes_page:
                if quiz['html_url'].replace('https://canvas.harvard.edu/courses/','')[0:6] == course:
                    if 'Consolidation' in quiz['title']:
                        quiz_dict[str(course)][str(quiz['id'])] = quiz['title']
                else:
                    pass
            if "next" not in response.links:
                break  # No more pages to fetch
            page += 1
        except requests.exceptions.RequestException as e:
            print(f"Error fetching quizzes for course {course}: {e}")
        
        sorted_quiz_dict = dict(sorted(quiz_dict[course].items(), key=lambda item: item[1]))

    return sorted_quiz_dict


# Load JSON data into a DataFrame
def load_json_to_dataframe(json_file):
    with open(json_file, 'r') as f:
        data = json.load(f)
    newdf = pd.DataFrame(data)
    return newdf

def extract_text(html):
    # Regex pattern to match the text between the tags
    pattern = re.compile(r'>\s*([^<]+?)\s*<')

    # Find all matches
    matches = pattern.findall(html)

    # Join the matches to form the complete extracted text
    extracted_text = ' '.join(matches).strip()

    return extracted_text

# Function to compare two dataframes and find differences
def check_new_data(course, quiz, apikey, azurekey, endpoint):
    headers = {"Authorization": f"Bearer {api_key}"}
    pre_graded_df = pd.read_json('Code/Data/graded_quizzes.json')
    un_graded = []

    try:
        url = f"https://canvas.harvard.edu/api/v1/courses/{course}/quizzes/{quiz}"
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an exception for 4xx/5xx status codes
        quiz_page = json.loads(response.text)  # Convert response text to dictionary using json.loads()
        assignment_id = quiz_page['assignment_id']

        url = f"https://canvas.harvard.edu/api/v1/courses/{course}/quizzes/{quiz}/questions"
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an exception for 4xx/5xx status codes
        questions_page = json.loads(response.text)  # Convert response text to dictionary using json.loads()
        questions_df = pd.DataFrame.from_dict(questions_page)
        questions_df = questions_df[(questions_df['question_type']=="essay_question")]

        page = 1
        while True:
            url = f"https://canvas.harvard.edu/api/v1/courses/{course}/assignments/{assignment_id}/submissions"
            params = {"page": page, "include[]":"submission_history","per_page":"100"}

            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()  # Raise an exception for 4xx/5xx status codes
            submissions_page = json.loads(response.text)  # Convert response text to dictionary using json.loads()
            for user_submission in submissions_page:
                submission_id = user_submission['id']
                student_score = user_submission['score']
                attempt = user_submission['attempt']

                check_if_graded = pre_graded_df[(pre_graded_df['submission_id']==submission_id)]

                if user_submission['submission_history'][0].get('submission_data'):
                    for submission_data in user_submission['submission_history'][0].get('submission_data'):
                        write_dict = {'quiz_id':'', 
                                    'quiz_type':'', 
                                    'quiz_title':'',
                                    'history_id':'',
                                    'submission_id':'',
                                    'student_score':'',
                                    'quiz_question_count':'',
                                    'quiz_points_possible':'',
                                    'question_points_possible':'',
                                    'answer_points_scored':'',
                                    'attempt':'',
                                    'question_name':'',
                                    'question_type':'',
                                    'question_text':'',
                                    'question_answer':'',
                                    'student_answer':'',
                                    'course_id':'',
                                    'accuracy':'',
                                    'completeness':''}

                        if check_if_graded.empty:
                            #from quiz_page
                            write_dict['quiz_id'] = quiz
                            write_dict['quiz_type'] = quiz_page['quiz_type']
                            write_dict['quiz_title'] = quiz_page['title']
                            write_dict['quiz_question_count'] = quiz_page['question_count']
                            write_dict['quiz_points_possible'] = quiz_page['points_possible']
                            write_dict['question_points_possible'] = quiz_page['points_possible']
        
                            #from questions_df
                            questions_df_filtered = questions_df[(questions_df['id']==submission_data['question_id']) 
                                                                & (questions_df['quiz_id']==int(quiz))]
                            
                            write_dict['question_text'] = extract_text(questions_df_filtered['question_text'].item())
                            write_dict['question_name'] = questions_df_filtered['question_name'].item()
                            write_dict['question_type'] = questions_df_filtered['question_type'].item()
                            write_dict['question_answer'] = questions_df_filtered['neutral_comments'].item()                 

                            #from submission_data
                            write_dict['history_id'] = submission_data['question_id']
                            write_dict['answer_points_scored'] = submission_data['points']
                            write_dict['student_answer'] = submission_data['text']
                            write_dict['attempt'] = attempt
                            write_dict['submission_id'] = submission_id
                            write_dict['student_score'] = student_score
                            write_dict['course_id'] = course

                            accuracy, completeness = grade_answer(write_dict['student_answer'], write_dict['question_answer'], azurekey, endpoint)
                            write_dict['accuracy'] = accuracy
                            write_dict['completeness'] = completeness
                            
                            #reorder the columns
                            write_dict = pd.DataFrame.from_records(write_dict, index=[0])
                            write_dict = write_dict[pre_graded_df.columns]
                            write_dict = write_dict.to_dict('records')[0]
                            
                            un_graded.append(write_dict)

                        else:
                            pass

            if "next" not in response.links:
                break  # No more pages to fetch
            page += 1
            
    except requests.exceptions.RequestException as e:
        print(f"Error fetching quizzes for course {course}: {e}")
        
    if len(un_graded) > 0:
        with open('Code/Data/graded_quizzes.json', "r") as file:
            data = file.read()[:-1]
        with open('Code/Data/graded_quizzes.json', "w") as file:
            file.write(data)
            file.write(',')
        with open('Code/Data/graded_quizzes.json', "a") as outfile:
            for record in un_graded:
                if record == un_graded[-1]:
                    json.dump(record, outfile, indent=2)                
                else:
                    json.dump(record, outfile, indent=2)
                    outfile.write(',')
                    outfile.write('\n')
            outfile.write(']')

def grade_answer(student_answer, correct_answer, azurekey, endpoint):
    prompt = "Compare the student answer to the correct answer. Rate the accuracy (a measure of how correct the student is) and completeness (did the student identify all components of the question) of the student answer according to these scales: Accuracy Options: 1 - not accurate, 2 - somewhat accurate, 3 - mostly accurate, 4 - completely accurate. Completeness: 1 - incomplete, 2 - partially complete, 3 - mostly complete, 4 - complete. Explain your answer briefly. Format your answer as a list separated by |. Example: 3|4|explanation" +f"Student Answer:{student_answer}\nCorrect Answer:{correct_answer}."

    client = AzureOpenAI(
            api_key = azurekey,
            azure_endpoint = endpoint,
            api_version = "2024-04-01-preview"
        )

    response = client.chat.completions.create(  model = "gpt-4o",
                                                messages=[
                                                    {"role": "system", "content": "You are a helpful course Teaching Assistant."},
                                                    {"role": "user", "content": f"{prompt}"}
                                                ]
                                            )

    grade = response.choices[0].message.content.split('|')

    accuracy = grade[0]
    completeness = grade[1]

    return accuracy, completeness


def instructor_feedback(course, quiz, azurekey, endpoint):
    
    #sort/group the student scores into buckets
    df = pd.read_json('Code/Data/graded_quizzes.json')

    # Filter the DataFrame
    subset = df[(df['quiz_id'] == int(quiz)) & (df['course_id'] == int(course))]
    questions = list(subset['question_name'].unique())
    quiz_group = subset['quiz_title'].unique().item().split(' ')[0]
    
    question = questions[0]
    # for question in questions:
    
    question_subset = subset[subset['question_name'] == question]
    
    # Initialize an empty dictionary to hold the buckets
    buckets = {}

    for accuracy_value in [1, 2, 3, 4]:
        # Group the 'subset' into buckets based on 'accuracy' value
        buckets[accuracy_value] = question_subset[question_subset['accuracy'] == accuracy_value]

    for accuracy_value, bucket in buckets.items():
        break

    student_answers = list(bucket['student_answer'])
    correct_answer = bucket['question_answer'].item()
    
    prompt = f"The following students all received a {accuracy_value} for accuracy on a scale of 1-4 when compared to the correct answer. Come up with a summary in 100 words or less of why they received the score they did, what concepts they most frequently missed, and what concepts they most frequently got correct. \n Student answers:{student_answers} \n Correct answer: {correct_answer}."

    client = AzureOpenAI(
            api_key = azurekey,
            azure_endpoint = endpoint,
            api_version = "2024-04-01-preview"
        )

    response = client.chat.completions.create(  model = "gpt-4o",
                                                messages=[
                                                    {"role": "system", "content": "You are a helpful course Teaching Assistant designed to provide helpful feedback to an Instructor regarding how their students are performing on quizzes."},
                                                    {"role": "user", "content": f"{prompt}"}
                                                ]
                                            )

    question_feedback = response.choices[0].message.content
    return question_feedback
    #level_one_feedback()

    #level_two_feedback()

    #level_three_feedback()

#TODO: ideas for instructor feedback:
#Hierarchical
#Do the same as the grading, turn it into a prompt
#Grey's Idea
#Sort the student scores so you have all the poor performing ones on one end
#and the good performing ones are on the other. 
#Level one: why did the ones get ones? twos get twos?
#Level two: Concepts missed/correct per group
#Level three: Overall concepts missed/correct
#Level four: Report
#Add a word limit in 500 words or less in the prompt




#GRAPHS

def accuracy_per_question_bar(course, quiz):
    # Load the JSON data
    df = pd.read_json('Code/Data/graded_quizzes.json')

    # Filter the DataFrame
    subset = df[(df['quiz_id'] == int(quiz)) & (df['course_id'] == int(course))]
    quiz_group = subset['quiz_title'].unique().item().split(' ')[0]

    # Count the number of students who scored 1, 2, 3, or 4 per question
    score_counts = subset.groupby(['question_name', 'accuracy']).size().unstack(fill_value=0).reset_index()

    # Normalize the counts as a percentage of the total responses per question
    score_counts.set_index('question_name', inplace=True)
    score_percentages = score_counts.div(score_counts.sum(axis=1), axis=0).reset_index()

    # Create a plotly figure
    fig = go.Figure()

    # Plot each score group as a separate bar series
    for score in [1, 2, 3, 4]:
        if score in score_percentages.columns:
            fig.add_trace(go.Bar(
                x=score_percentages['question_name'],
                y=score_percentages[score] * 100,  # Convert to percentage
                name=f'Accuracy Score {score}',
                text=(score_percentages[score] * 100).round(2).astype(str) + '%',
                textposition='auto',
                hoverinfo='none'  # Disable hover data
            ))

    # Update layout
    fig.update_layout(
        title=f'Students per Accuracy Score Group - {quiz_group}',
        xaxis_title='Question Name',
        yaxis_title='Percentage of Scores',
        barmode='group',  # Group bars together
        margin=dict(l=40, r=40, t=40, b=40)
    )

    return fig

def completeness_per_question_bar(course, quiz):
    # Load the JSON data
    df = pd.read_json('Code/Data/graded_quizzes.json')

    # Filter the DataFrame
    subset = df[(df['quiz_id'] == int(quiz)) & (df['course_id'] == int(course))]
    quiz_group = subset['quiz_title'].unique().item().split(' ')[0]

    # Count the number of students who scored 1, 2, 3, or 4 per question
    score_counts = subset.groupby(['question_name', 'completeness']).size().unstack(fill_value=0).reset_index()

    # Normalize the counts as a percentage of the total responses per question
    score_counts.set_index('question_name', inplace=True)
    score_percentages = score_counts.div(score_counts.sum(axis=1), axis=0).reset_index()

    # Create a plotly figure
    fig = go.Figure()

    # Plot each score group as a separate bar series
    for score in [1, 2, 3, 4]:
        if score in score_percentages.columns:
            fig.add_trace(go.Bar(
                x=score_percentages['question_name'],
                y=score_percentages[score] * 100,  # Convert to percentage
                name=f'Completeness Score {score}',
                text=(score_percentages[score] * 100).round(2).astype(str) + '%',
                textposition='auto',
                hoverinfo='none'  # Disable hover data
            ))

    # Update layout
    fig.update_layout(
        title=f'Students per Completeness Score Group - {quiz_group}',
        xaxis_title='Question Name',
        yaxis_title='Percentage of Scores',
        barmode='group',  # Group bars together
        margin=dict(l=40, r=40, t=40, b=40)
    )

    return fig

def avg_of_scores_hist(course, quiz):
    # Load the JSON data
    df = pd.read_json('Code/Data/graded_quizzes.json')

    # Filter the DataFrame
    subset = df[(df['quiz_id'] == int(quiz)) & (df['course_id'] == int(course))]

    quiz_group = subset['quiz_title'].unique().item().split(' ')[0]
    
    # Calculate average accuracy and completeness per question
    average_metrics = subset.groupby('question_name')[['accuracy', 'completeness']].mean().reset_index()
    average_metrics['accuracy'] = average_metrics['accuracy'].round(2)
    average_metrics['completeness'] = average_metrics['completeness'].round(2)

    fig = go.Figure()

    # Add accuracy bars
    fig.add_trace(go.Bar(
        x=average_metrics['question_name'],
        y=average_metrics['accuracy'],
        name='Accuracy',
        text=average_metrics['accuracy'],
        textposition='auto'
    ))

    # Add completeness bars
    fig.add_trace(go.Bar(
        x=average_metrics['question_name'],
        y=average_metrics['completeness'],
        name='Completeness',
        text=average_metrics['completeness'],
        textposition='auto'
    ))

    fig.update_layout(
        title=f'Average Accuracy and Completeness per Question - {quiz_group}',
        xaxis_title='Question Name',
        yaxis_title='Average Score',
        barmode='group',  # Group bars next to each other
        margin=dict(l=40, r=40, t=40, b=40)
    )

    return fig

def accuracy(course, quiz):
    # Load the JSON data
    df = pd.read_json('Code/Data/graded_quizzes.json')

    # Filter the DataFrame
    subset = df[(df['quiz_id'] == int(quiz)) & (df['course_id'] == int(course))]
    quiz_group = subset['quiz_title'].unique().item().split(' ')[0]

    # Filter for quizzes with the same quiz group in the title
    quiz_group_subset = df[df['quiz_title'].str.startswith(quiz_group)]

    # Calculate average total accuracy per quiz
    average_accuracy_per_quiz = quiz_group_subset.groupby('quiz_title')['accuracy'].mean().reset_index()

    # Round the averages to the nearest hundredth
    average_accuracy_per_quiz['accuracy'] = average_accuracy_per_quiz['accuracy'].round(2)

    # Extract the numerical part of the quiz titles for proper sorting
    average_accuracy_per_quiz['quiz_num'] = average_accuracy_per_quiz['quiz_title'].str.extract(r'(\d+)').astype(int)

    # Sort the dataframe by the numerical part of the quiz titles
    average_accuracy_per_quiz = average_accuracy_per_quiz.sort_values(by='quiz_num')

    # Create a plotly figure
    fig = go.Figure()

    # Plot the average accuracy per quiz
    fig.add_trace(go.Scatter(
        x=average_accuracy_per_quiz['quiz_title'], 
        y=average_accuracy_per_quiz['accuracy'], 
        mode='lines+markers', 
        name='Average Accuracy',
        hoverinfo='text',
        text=average_accuracy_per_quiz['accuracy']))

    # Add trend line using linear regression
    X = average_accuracy_per_quiz['quiz_num'].values.reshape(-1, 1)
    y = average_accuracy_per_quiz['accuracy'].values

    # Fit linear regression model
    model = LinearRegression()
    model.fit(X, y)
    trend_line = model.predict(X)

    fig.add_trace(go.Scatter(
        x=average_accuracy_per_quiz['quiz_title'],
        y=trend_line,
        mode='lines',
        name='Average Total Accuracy Over Time',
        line=dict(dash='dash')
    ))

    # Update layout
    fig.update_layout(
        title=f'Average Total Accuracy for {quiz_group} Quizzes',
        xaxis_title='Quiz Title',
        yaxis_title='Average Total Accuracy',
        margin=dict(l=40, r=40, t=40, b=40)
    )

    return fig

def completeness(course, quiz):
    # Load the JSON data
    df = pd.read_json('Code/Data/graded_quizzes.json')

    # Filter the DataFrame
    subset = df[(df['quiz_id'] == int(quiz)) & (df['course_id'] == int(course))]
    quiz_group = subset['quiz_title'].unique().item().split(' ')[0]

    # Filter for quizzes with the same quiz group in the title
    quiz_group_subset = df[df['quiz_title'].str.startswith(quiz_group)]

    # Calculate average total completeness per quiz
    average_completeness_per_quiz = quiz_group_subset.groupby('quiz_title')['completeness'].mean().reset_index()

    # Round the averages to the nearest hundredth
    average_completeness_per_quiz['completeness'] = average_completeness_per_quiz['completeness'].round(2)

    # Extract the numerical part of the quiz titles for proper sorting
    average_completeness_per_quiz['quiz_num'] = average_completeness_per_quiz['quiz_title'].str.extract(r'(\d+)').astype(int)

    # Sort the dataframe by the numerical part of the quiz titles
    average_completeness_per_quiz = average_completeness_per_quiz.sort_values(by='quiz_num')

    # Create a plotly figure
    fig = go.Figure()

    # Plot the average completeness per quiz
    fig.add_trace(go.Scatter(
        x=average_completeness_per_quiz['quiz_title'], 
        y=average_completeness_per_quiz['completeness'], 
        mode='lines+markers', 
        name='Average Completeness',
        hoverinfo='text',
        text=average_completeness_per_quiz['completeness']))

    # Add trend line using linear regression
    X = average_completeness_per_quiz['quiz_num'].values.reshape(-1, 1)
    y = average_completeness_per_quiz['completeness'].values

    # Fit linear regression model
    model = LinearRegression()
    model.fit(X, y)
    trend_line = model.predict(X)

    fig.add_trace(go.Scatter(
        x=average_completeness_per_quiz['quiz_title'],
        y=trend_line,
        mode='lines',
        name='Average Total Completeness Over Time',
        line=dict(dash='dash')
    ))

    # Update layout
    fig.update_layout(
        title=f'Average Total Completeness for {quiz_group} Quizzes',
        xaxis_title='Quiz Title',
        yaxis_title='Average Total completeness',
        margin=dict(l=40, r=40, t=40, b=40)
    )

    return fig



#Data Quality Issue: Make CBB10 == CBB 10, same quiz just messy data

#Filter by question

#level one feedback: per bin
#level two feedback: per question
#level three feedback: per quiz
#level four feedback: per quiz group

#download report button
