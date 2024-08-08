# -*- coding: utf-8 -*-
import matplotlib
import pandas as pd
from helpers import  (check_new_data,
                      accuracy,
                      completeness,
                      accuracy_per_question_bar,
                      completeness_per_question_bar,
                      avg_of_scores_hist,
                      instructor_feedback,
                      get_courses,
                      get_quizzes)
from shiny.express import input, output, render, ui
from shiny import reactive
from shinywidgets import output_widget, render_widget 
import os
matplotlib.use("agg")

ui.tags.style(
    """
    /* Don't apply fade effect, it's constantly recalculating */
    .recalculating, .recalculating > * {
        opacity: 1 !important;
    }
    """
)

ui.busy_indicators.use(spinners=False, pulse=True)

with ui.sidebar():
    ui.input_password("apikey", "Canvas API Key:", "")
    ui.input_action_button("go", "Go"),

    ui.input_selectize(
        "course",
        "Choose Course",
        choices={
            "test": "",}
    )

    ui.input_action_button("next", "Next"),

    ui.input_selectize(
        "cae",
        "Choose CAE",
        choices={
            "test": "",}
    )


    ui.input_action_button("generate", "Generate Reports"),

    #API key entry to fetch all courses
    @reactive.effect
    @reactive.event(input.go)
    def _():
        if input.apikey() == "":
            print("Please Enter a valid API Key")
        else:
            courses_dict = get_courses(input.apikey())
            ui.update_selectize("course", choices=courses_dict)

    #Choose the course
    @reactive.effect
    @reactive.event(input.next)
    def _():
        if input.course():
            quiz_dict = get_quizzes(input.apikey(), input.course())
            ui.update_selectize("cae", choices=quiz_dict)      
        else:
            print("No course input")

with ui.panel_absolute(width="75%"):
    # Enable busy indicators
    with ui.navset_bar(title="Student Performance"):
        @reactive.event(input.generate)
        def _():
            check_new_data(input.course(), input.cae(), input.apikey(), os.environ.get("azure_key"), os.environ.get("endpoint"))     

        with ui.nav_panel(title="Start Guide"):
            @render.text
            def text():
                return '''Welcome to ALAS
                          '''
            @render.text
            def text2():
                return '''To get started, please visit https://canvas.harvard.edu/, go to your profile settings, and create a new access token. 
                          This is your unique API key that should not be shared with anyone.
                          '''
                        
            @render.text
            def text3():
                return '''Once you have this key copied/saved in a secure location, paste it into the API key box to get started.
                          '''


        with ui.nav_panel(title="Graphs"):
            @render_widget
            @reactive.event(input.generate)
            def plot_average_accuracy_per_question_bar():
                return accuracy_per_question_bar(input.course(), input.cae())


            @render_widget
            @reactive.event(input.generate)
            def plot_completeness_accuracy_per_question_bar():
                return completeness_per_question_bar(input.course(), input.cae())


            @render_widget
            @reactive.event(input.generate)
            def plot_avg_of_scores_hist():
                return avg_of_scores_hist(input.course(), input.cae())


            @render_widget
            @reactive.event(input.generate)
            def plot_accuracy():
                return accuracy(input.course(), input.cae())


            @render_widget
            @reactive.event(input.generate)
            def plot_completeness():
                return completeness(input.course(), input.cae())


        with ui.nav_panel(title="Topics"):
            @render.text
            @reactive.event(input.generate)
            def feedback():
                return instructor_feedback(input.course(), input.cae(), os.environ.get("azure_key"), os.environ.get("endpoint"))

        with ui.nav_panel(title="Source Data"):
            @render.download(label="Download CSV", filename="data.csv")
            @reactive.event(input.download)
            def _():
                df = pd.read_json('Data/graded_quizzes.json')
                subset = df[(df['quiz_id']==int(input.cae())) & (df['course_id']==int(input.course()))]
                yield subset.to_csv()

            @render.data_frame
            @reactive.event(input.generate)
            def table():
                df = pd.read_json('Data/graded_quizzes.json')
                subset = df[(df['quiz_id']==int(input.cae())) & (df['course_id']==int(input.course()))]
                return render.DataGrid(subset)
