# -*- coding: utf-8 -*-
"""Helper functions for app.py to create plots and create instructor feedback."""

from __future__ import print_function
import json
import re
import pandas as pd
from openai import AzureOpenAI
import requests
import plotly.graph_objects as go
from sklearn.linear_model import LinearRegression


def get_courses(api_key):
    """
    Fetches the list of courses from the Canvas API.

    Args:
        api_key (str): The API key for authentication.

    Returns:
        courses_dict (dict): A dictionary of course IDs and their corresponding names.
    """
    base_url = "https://canvas.harvard.edu/api/v1/courses"
    headers = {"Authorization": f"Bearer {api_key}"}
    courses_dict = {}
    page = 1

    while True:
        params = {"page": page}
        try:
            response = requests.get(base_url, headers=headers, params=params, timeout=15)
            response.raise_for_status()  # Raise an exception for 4xx/5xx status codes
            courses_page = json.loads(response.text)  # Convert response text to dict
            for course in courses_page:
                courses_dict[str(course['id'])] = course['name']
            if "next" not in response.links:
                break  # No more pages to fetch
            page += 1
        except requests.exceptions.RequestException as e:
            print("Error fetching courses:", e)
            break

    return courses_dict


def get_quizzes(api_key, course):
    """
    Fetches the list of quizzes for a specific course from the Canvas API.

    Args:
        api_key (str): The API key for authentication.
        course (str): The course ID.

    Returns:
        sorted_quiz_dict (dict): A dictionary containing the quizzes for the given course.
    """
    quiz_dict = {}
    quiz_dict[str(course)] = {}
    base_url = "https://canvas.harvard.edu/api/v1/courses/"
    course_api = f"{course}/quizzes"
    headers = {"Authorization": f"Bearer {api_key}"}
    page = 1
    while True:
        params = {"page": page, "per_page":"100"}
        try:
            response = requests.get(base_url+course_api, headers=headers, params=params, timeout=15)
            response.raise_for_status()  # Raise an exception for 4xx/5xx status codes
            quizzes_page = json.loads(response.text)  # Convert response text to dict
            for quiz in quizzes_page:
                if quiz['html_url'].replace(base_url,'')[0:6] == course:
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


def extract_text(html):
    """
    Extracts text from malformatted string returned from Canvas API.
    
    Args:
        html (str): The html string to be parsed.

    Returns:
        extracted_text (str): A string of the plain text extracted from the html.
    """


    pattern = re.compile(r'>\s*([^<]+?)\s*<') # Regex pattern for text between html tags

    matches = pattern.findall(html) # Find all matches

    extracted_text = ' '.join(matches).strip() # Join the matches

    return extracted_text


def check_new_data(course, quiz, apikey, azurekey, endpoint):
    """
    Checks for un-graded assessment submissions in the Canvas API.
    
    Args:
        course (str): The selected course ID.
        quiz (str): The selected quiz ID.
        apikey (str): The canvas API key.
        azurekey (str): The Azure API key.
        endpoint (str): The Azure endpoint.

    Returns:
        None
    """
    headers = {"Authorization": f"Bearer {apikey}"}
    pre_graded_df = pd.read_json('Data/graded_quizzes.json')
    un_graded = []
    base_url = "https://canvas.harvard.edu/api/v1/courses/"

    try:
        url = f"{base_url}{course}/quizzes/{quiz}"
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()  # Raise an exception for 4xx/5xx status codes
        quiz_page = json.loads(response.text)  # Convert response text to dict
        assignment_id = quiz_page['assignment_id']

        url = f"{base_url}{course}/quizzes/{quiz}/questions"
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()  # Raise an exception for 4xx/5xx status codes
        questions_page = json.loads(response.text)  # Convert response text to dict
        qdf = pd.DataFrame.from_dict(questions_page)
        qdf = qdf[(qdf['question_type']=="essay_question")]

        page = 1
        while True:
            url = f"{base_url}{course}/assignments/{assignment_id}/submissions"
            params = {"page": page, "include[]":"submission_history","per_page":"100"}

            response = requests.get(url, headers=headers, params=params, timeout=15)
            response.raise_for_status()  # Raise an exception for 4xx/5xx status codes
            submissions_page = json.loads(response.text)  # Convert response text to dict
            for user_submission in submissions_page:
                submission_id = user_submission['id']
                student_score = user_submission['score']
                attempt = user_submission['attempt']

                check_if_graded = pre_graded_df[(pre_graded_df['submission_id']==submission_id)]

                if user_submission['submission_history'][0].get('submission_data'):
                    submission = user_submission['submission_history'][0].get('submission_data')
                    for user_data in submission:
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
                            qdf_filtered = qdf[(qdf['id']==user_data['question_id'])
                                                                & (qdf['quiz_id']==int(quiz))]

                            write_dict['question_text'] = extract_text(qdf_filtered['question_text'].item())
                            write_dict['question_name'] = qdf_filtered['question_name'].item()
                            write_dict['question_type'] = qdf_filtered['question_type'].item()
                            write_dict['question_answer'] = qdf_filtered['neutral_comments'].item()

                            #from submission_data
                            write_dict['history_id'] = user_data['question_id']
                            write_dict['answer_points_scored'] = user_data['points']
                            write_dict['student_answer'] = user_data['text']
                            write_dict['attempt'] = attempt
                            write_dict['submission_id'] = submission_id
                            write_dict['student_score'] = student_score
                            write_dict['course_id'] = course
                            accuracy, completeness = grade_answer(write_dict['student_answer'],
                                                                  write_dict['question_answer'],
                                                                  azurekey,
                                                                  endpoint)
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
        with open('Data/graded_quizzes.json', "r") as file:
            data = file.read()[:-1]
        with open('Data/graded_quizzes.json', "w") as file:
            file.write(data)
            file.write(',')
        with open('Data/graded_quizzes.json', "a") as outfile:
            for record in un_graded:
                if record == un_graded[-1]:
                    json.dump(record, outfile, indent=2)
                else:
                    json.dump(record, outfile, indent=2)
                    outfile.write(',')
                    outfile.write('\n')
            outfile.write(']')

def grade_answer(student_answer, correct_answer, azurekey, endpoint):
    """
    Compares the student answer to the correct answer and assigns it a score for
    accuracy and compeleteness.
    
    Args:
        student_answer (str): The students response to the question.
        correct_answer (str): The correct answer to the question.
        azurekey (str): The Azure API key.
        endpoint (str): The Azure endpoint.

    Returns:
        accuracy (str): a score for how accurate the students response was
        completeness (str): a score for how complete the students response was
    """

    prompt = ('Compare the student answer to the correct answer. '
              'Rate the accuracy (a measure of how correct the student is) '
              'and completeness (did the student identify all components of the '
              'question) of the student answer according to these scales: '
              'Accuracy Options: 1 - not accurate, 2 - somewhat accurate, '
              '3 - mostly accurate, 4 - completely accurate. Completeness: '
              '1 - incomplete, 2 - partially complete, 3 - mostly complete, '
              '4 - complete. Explain your answer briefly. Format your answer '
              'as a list separated by |. Example: 3|4|explanation" +f"Student '
              f'Answer:{student_answer}\nCorrect Answer:{correct_answer}.')

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
    """
    Bins all grades for all questions on a quiz, and outputs summative feedback 
    of all students performance.

    Args:
        course (str): The course ID.
        quiz (str): The quiz ID.
        azurekey (str): The Azure API key.
        endpoint (str): The Azure endpoint.

    Returns:
        level_three_feedback (str): a summary of all students performance
    """

    df = pd.read_json('Data/graded_quizzes.json')

    # Filter the DataFrame
    subset = df[(df['quiz_id'] == int(quiz)) & (df['course_id'] == int(course))]
    questions = list(subset['question_name'].unique())
    quiz_group = subset['quiz_title'].unique().item().split(' ')[0]

    level_one = {}
    level_two = {}

    for question in questions:
        # Group the 'subset' into buckets based on 'accuracy' value
        level_one[question] = level_one_feedback(question, subset, azurekey, endpoint)
        level_two[question] = level_two_feedback(level_one[question], question, azurekey, endpoint)

    return level_three_feedback(level_two, azurekey, endpoint)


def level_one_feedback(question, subset, azurekey, endpoint):
    """
    Bins all grades for each question on a quiz, and outputs a summary string for each bin
    containing what students did well/not well on per question

    Args:
        question (str): The question name being graded (Question 1, Question 2, etc.).
        subset (str): The subset df of all graded data.
        azurekey (str): The Azure API key.
        endpoint (str): The Azure endpoint.

    Returns:
        l1_feedback (list): a list of feedback strings per question
    """
    question_subset = subset[subset['question_name'] == question]

    # Initialize an empty dictionary to hold the buckets
    buckets = {}
    l1_feedback = []
    for accuracy_value in [1, 2, 3, 4]:
        # Group the 'subset' into buckets based on 'accuracy' value
        buckets[accuracy_value] = question_subset[question_subset['accuracy'] == accuracy_value]

    for accuracy_value, bucket in buckets.items():
        if len(bucket) == 0:
            l1_feedback.append(f"No students received a {accuracy_value} for this question.")
        else:
            student_answers = list(bucket['student_answer'])
            correct_answer = bucket['question_answer'].unique().item()
            prompt = (f'The following students all received a {accuracy_value} for accuracy'
                       'on a scale of 1-4 when compared to the correct answer. Come up with'
                       'a summary in 100 words or less of why they received that score, what'
                       'concepts they most frequently missed, and what concepts they most '
                       'frequently got correct. '
                       f'Student answers:{student_answers}'
                       f'Correct answer: {correct_answer}.')

            client = AzureOpenAI(
                    api_key = azurekey,
                    azure_endpoint = endpoint,
                    api_version = "2024-04-01-preview"
                )

            response = client.chat.completions.create(
                    model = "gpt-4o",
                    messages=[
                    {"role": "system", "content": ('You are a helpful course Teaching Assistant '
                                                    'designed to provide helpful feedback to an '
                                                    'Instructor regarding how their students are '
                                                    'performing on quizzes.')},
                    {"role": "user", "content": f"{prompt}"}
                    ]
                    )

            question_feedback = response.choices[0].message.content
            l1_feedback.append(question_feedback)
    return l1_feedback


def level_two_feedback(level_one, question, azurekey, endpoint):
    """
    Combines level one feedback to give a summary of how students did per question

    Args:
        level_one (list): A list of summaries for each grade bin.
        question (str): The name of the question.
        azurekey (str): The Azure API key.
        endpoint (str): The Azure endpoint.

    Returns:
        l2_feedback (str): a summary feedback string
    """

    prompt = ('Summarize the following feedback for {question}. '
              'Include what students most frequently missed, and '
              'what they most frequently correctly identified. {level_one}.')

    client = AzureOpenAI(
            api_key = azurekey,
            azure_endpoint = endpoint,
            api_version = "2024-04-01-preview"
        )

    response = client.chat.completions.create(
                model = "gpt-4o",
                messages=[
                    {"role": "system", "content": ('You are a helpful course Teaching Assistant'
                                                   'designed to provide helpful feedback to an '
                                                   'Instructor regarding how their students are '
                                                   'performing on quizzes.')},
                    {"role": "user", "content": f"{prompt}"}
                ]
            )

    l2_feedback = response.choices[0].message.content
    return l2_feedback


def level_three_feedback(level_two, azurekey, endpoint):
    """
    Combines level two feedback to give a summary of student performance per quiz

    Args:
        level_two (str): a summary of how students did per question.
        azurekey (str): The Azure API key.
        endpoint (str): The Azure endpoint.

    Returns:
        l1_feedback (list): a list of feedback strings per question
    """

    prompt = ('Summarize the feedback provided in less than 100 words. '
              'Example summary: "For this assessment exercise, students '
              'correctly identified concept A, B, and C. Students struggled'
              ' to identify D, and lacked a detailed understanding of X. '
              'Exact mechanisms of Z were not well described. Overall, '
              'students have a solid grasp of basic concepts, but need '
              'more focus on understanding specific processes." '
              f'Feedback: {level_two}.')

    client = AzureOpenAI(
            api_key = azurekey,
            azure_endpoint = endpoint,
            api_version = "2024-04-01-preview"
        )

    response = client.chat.completions.create(
        model = "gpt-4o",
        messages=[
            {"role": "system", "content": ('You are a helpful course Teaching Assistant '
                                           'designed to provide helpful feedback to an '
                                           'Instructor regarding how their students are '
                                           'performing on quizzes.')},
            {"role": "user", "content": f"{prompt}"}
        ]
    )

    question_feedback = response.choices[0].message.content
    return question_feedback


def accuracy_per_question_bar(course, quiz):
    """
    Generate a bar plot for accuracy per question.
    
    Parameters:
    course_id (int): The course identifier.
    quiz_id (int): The quiz identifier.

    Returns:
    plot: A bar plot of accuracy per question.
    """

    df = pd.read_json('Data/graded_quizzes.json')

    subset = df[(df['quiz_id'] == int(quiz)) & (df['course_id'] == int(course))] # Filter the df
    quiz_group = subset['quiz_title'].unique().item().split(' ')[0]

    score_counts = subset.groupby(['question_name', 'accuracy']).size().unstack(fill_value=0).reset_index() # Count students who scored 1, 2, 3, or 4 per question

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
    """
    Generate a bar plot for completeness per question.
    
    Parameters:
    course_id (int): The course identifier.
    quiz_id (int): The quiz identifier.

    Returns:
    plot: A bar plot of completeness per question.
    """

    # Load the JSON data
    df = pd.read_json('Data/graded_quizzes.json')

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
    """
    Generate a histogram for the distribution of scores.
    
    Parameters:
    course_id (int): The course identifier.
    quiz_id (int): The quiz identifier.

    Returns:
    plot: A histogram of the distribution of scores.
    """

    # Load the JSON data
    df = pd.read_json('Data/graded_quizzes.json')

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
    """
    Generate a line plot for accuracy across similar questions.
    
    Parameters:
    course_id (int): The course identifier.
    quiz_id (int): The quiz identifier.

    Returns:
    plot: A line plot of accuracy across similar questions.
    """

    # Load the JSON data
    df = pd.read_json('Data/graded_quizzes.json')

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

    x = average_accuracy_per_quiz['quiz_num'].values.reshape(-1, 1)
    y = average_accuracy_per_quiz['accuracy'].values

    model = LinearRegression()
    model.fit(x, y)
    trend_line = model.predict(x)

    fig.add_trace(go.Scatter(
        x=average_accuracy_per_quiz['quiz_title'],
        y=trend_line,
        mode='lines',
        name='Average Total Accuracy Over Time',
        line=dict(dash='dash')
    ))

    fig.update_layout(
        title=f'Average Total Accuracy for {quiz_group} Quizzes',
        xaxis_title='Quiz Title',
        yaxis_title='Average Total Accuracy',
        margin=dict(l=40, r=40, t=40, b=40)
    )

    return fig

def completeness(course, quiz):
    """
    Generate a line plot for completeness across similar questions.
    
    Parameters:
    course_id (int): The course identifier.
    quiz_id (int): The quiz identifier.

    Returns:
    plot: A line plot of completeness across similar questions.
    """

    # Load the JSON data
    df = pd.read_json('Data/graded_quizzes.json')

    subset = df[(df['quiz_id'] == int(quiz)) & (df['course_id'] == int(course))] # Filter the df
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