import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timezone
from zoneinfo import ZoneInfo  # For Python 3.9 and above

# --- Apply Bruins Gold Accents with Lighter Background ---

# Define the Bruins' colors
bruins_gold = '#FFB81C'     # Bruins Gold
text_color = '#000000'      # Black text for readability
background_color = '#FFFFFF'  # White background
black_color = '#000000'      # Black color (for borders)

# Set the page configuration
st.set_page_config(
    page_title="Boston Bruins Game Day Insights",
    page_icon="🏒",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inject custom CSS to style the app
st.markdown(f"""
    <style>
    /* Background color */
    .stApp {{
        background-color: {background_color};
    }}

    /* Text color */
    html, body, [class*="css"]  {{
        color: {text_color};
        background-color: {background_color};
    }}

    /* Primary color (buttons, sliders, etc.) */
    .stButton>button, .stSlider>div {{
        background-color: {bruins_gold};
        color: {text_color};
    }}

    /* Header color */
    .css-10trblm {{
        color: {bruins_gold};
    }}

    /* Subheader color */
    .css-hxt7ib {{
        color: {bruins_gold};
    }}

    /* Dataframe styles */
    .css-1d391kg {{
        color: {text_color};
    }}

    /* Sidebar styles */
    .css-1lcbmhc, .css-12oz5g7 {{
        background-color: {background_color};
        color: {text_color};
    }}

    /* Scrollbar */
    ::-webkit-scrollbar {{
        width: 10px;
    }}
    ::-webkit-scrollbar-track {{
        background: {background_color};
    }}
    ::-webkit-scrollbar-thumb {{
        background: {bruins_gold};
    }}

    /* Adjust input widgets */
    .stTextInput>div>div>input, .stDateInput>div>div>input {{
        background-color: #F0F0F0;
        color: {text_color};
    }}

    /* Checkbox */
    .stCheckbox>div>div>div>input[type='checkbox']:checked + div>div {{
        background-color: {bruins_gold};
    }}

    /* Dataframe header */
    .css-1gx2w0r thead tr th {{
        background-color: #F0F0F0;
        color: {bruins_gold};
    }}

    /* Dataframe cells */
    .css-1gx2w0r tbody tr td {{
        background-color: #FFFFFF;
    }}
    </style>
    """, unsafe_allow_html=True)

# --- Load the data ---
df = pd.read_csv('bruins_game_history.csv')

# --- Data cleaning steps ---

# Rename columns for clarity
df = df.rename(columns={
    'Unnamed: 2': 'Location',
    'Unnamed: 6': 'Outcome',
    'Unnamed: 7': 'OT/SO',
    'Att.': 'Attendance',
    'LOG': 'Log',
    'Notes': 'Notes'
})

# Keep only the columns of interest
columns_to_keep = ['Season', 'GP', 'Date', 'Location', 'Opponent', 'GF', 'GA',
                   'Outcome', 'OT/SO', 'W', 'L', 'T', 'OL', 'Streak']
df = df[columns_to_keep]

# Convert 'Date' to datetime
df['Date'] = pd.to_datetime(df['Date'])

# Extract month, day, and day of the week
df['Month'] = df['Date'].dt.month
df['Day'] = df['Date'].dt.day
df['MM-DD'] = df['Date'].dt.strftime('%m-%d')
df['DayOfWeek'] = df['Date'].dt.day_name()

# Replace missing values in 'Location' with 'Home' and '@' with 'Away'
df['Location'] = df['Location'].fillna('Home')
df['Location'] = df['Location'].replace({'@': 'Away'})

# Convert numerical columns to numeric types
numerical_columns = ['GF', 'GA', 'W', 'L', 'T', 'OL', 'GP']
for col in numerical_columns:
    df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')

# Combine 'Outcome' and 'OT/SO' columns
df['Outcome'] = df['Outcome'].fillna('') + df['OT/SO'].fillna('')
df = df.drop(columns=['OT/SO'])  # Drop 'OT/SO' as it's now merged into 'Outcome'

# Standardize 'Outcome' values
def standardize_outcome(outcome):
    outcome = outcome.strip()
    if 'W' in outcome:
        if 'OT' in outcome:
            return 'Win OT'
        elif 'SO' in outcome:
            return 'Win SO'
        else:
            return 'Win'
    elif 'L' in outcome:
        if 'OT' in outcome:
            return 'Loss OT'
        elif 'SO' in outcome:
            return 'Loss SO'
        else:
            return 'Loss'
    elif 'T' in outcome:
        return 'Tie'
    else:
        return 'Unknown'

df['Outcome'] = df['Outcome'].apply(standardize_outcome)

# Create 'Win' column for easy calculations
df['Win'] = df['Outcome'].apply(lambda x: 1 if 'Win' in x else 0)

# Rearrange columns
df = df[['Season', 'GP', 'Date', 'Month', 'Day', 'MM-DD', 'DayOfWeek', 'Location', 'Opponent', 'Outcome', 'GF', 'GA',
         'W', 'L', 'T', 'OL', 'Streak', 'Win']]

# Reset index
df = df.reset_index(drop=True)

# --- Season Selection ---
st.sidebar.header("Select Season Range")

# Extract list of seasons
seasons = sorted(df['Season'].unique())

# Add season selection widgets
start_season = st.sidebar.selectbox("Start Season", seasons, index=0)
end_season = st.sidebar.selectbox("End Season", seasons, index=len(seasons)-1)

# Filter data based on selected seasons
season_filter = (df['Season'] >= start_season) & (df['Season'] <= end_season)
df_filtered = df[season_filter].reset_index(drop=True)

# --- Specify the Timezone ---
# Replace 'America/New_York' with your desired timezone
tz = ZoneInfo('America/New_York')

# --- Functions for data analysis ---

# Functions now accept the DataFrame as a parameter
def calculate_record_on_date(df, mm_dd, opponent=None):
    if opponent:
        games_on_date = df[(df['MM-DD'] == mm_dd) & (df['Opponent'] == opponent)]
    else:
        games_on_date = df[df['MM-DD'] == mm_dd]
    if games_on_date.empty:
        return None
    total_games = len(games_on_date)
    wins = int(games_on_date['Win'].sum())
    losses = int(len(games_on_date[games_on_date['Outcome'].str.contains('Loss')]))
    ties = int(len(games_on_date[games_on_date['Outcome'] == 'Tie']))
    win_percentage = round((wins / total_games) * 100, 2)
    return {
        'Total Games': total_games,
        'Wins': wins,
        'Losses': losses,
        'Ties': ties,
        'Win Percentage (%)': win_percentage
    }

def calculate_record_on_day(df, day_name, opponent=None):
    if opponent:
        games_on_day = df[(df['DayOfWeek'] == day_name) & (df['Opponent'] == opponent)]
    else:
        games_on_day = df[df['DayOfWeek'] == day_name]
    if games_on_day.empty:
        return None
    total_games = len(games_on_day)
    wins = int(games_on_day['Win'].sum())
    losses = int(len(games_on_day[games_on_day['Outcome'].str.contains('Loss')]))
    ties = int(len(games_on_day[games_on_day['Outcome'] == 'Tie']))
    win_percentage = round((wins / total_games) * 100, 2)
    return {
        'Total Games': total_games,
        'Wins': wins,
        'Losses': losses,
        'Ties': ties,
        'Win Percentage (%)': win_percentage
    }

def best_and_worst_day_against_opponent(df, opponent):
    opponent_games = df[df['Opponent'] == opponent]
    if opponent_games.empty:
        return None
    win_stats_by_day = opponent_games.groupby('DayOfWeek').agg(
        games_played=('Outcome', 'count'),
        wins=('Win', 'sum')
    )
    win_stats_by_day['Win Percentage (%)'] = (win_stats_by_day['wins'] / win_stats_by_day['games_played'] * 100).round(2)
    # Reorder days to match calendar order
    days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    win_stats_by_day = win_stats_by_day.reindex(days_order)
    win_stats_by_day = win_stats_by_day.dropna(subset=['games_played'])
    # Select best day considering highest win percentage and most games played
    max_win_percentage = win_stats_by_day['Win Percentage (%)'].max()
    best_days = win_stats_by_day[win_stats_by_day['Win Percentage (%)'] == max_win_percentage]
    best_day = best_days.sort_values('games_played', ascending=False).index[0]
    best_day_stats = best_days.loc[best_day]
    # Select worst day considering lowest win percentage and most games played
    min_win_percentage = win_stats_by_day['Win Percentage (%)'].min()
    worst_days = win_stats_by_day[win_stats_by_day['Win Percentage (%)'] == min_win_percentage]
    worst_day = worst_days.sort_values('games_played', ascending=False).index[0]
    worst_day_stats = worst_days.loc[worst_day]
    return (best_day, best_day_stats), (worst_day, worst_day_stats), win_stats_by_day

# --- App Interface ---

# Title and header
st.markdown(f"""
    <h1 style='text-align: center; color: {bruins_gold};'>
        Boston Bruins Game Day Insights
    </h1>
    """, unsafe_allow_html=True)

st.write(f"Displaying results for seasons {start_season} to {end_season}")

# --- Today's Date and Record ---

# Get the current date and time in the specified timezone
now = datetime.now(tz)
today = now.date()
today_mm_dd = today.strftime('%m-%d')
today_day_name = today.strftime('%A')

st.header(f"Today is {today.strftime('%B %d')}")
record_today = calculate_record_on_date(df_filtered, today_mm_dd)

if record_today:
    st.subheader(f"Bruins' Historical Record on {today.strftime('%B %d')}:")
    record_today_df = pd.DataFrame(record_today, index=[0])
    st.table(record_today_df)
else:
    st.write(f"No historical games found on {today.strftime('%B %d')} in the selected season range.")

# --- Record Based on Day of the Week ---
st.header(f"Today is {today_day_name}")
record_day = calculate_record_on_day(df_filtered, today_day_name)

if record_day:
    st.subheader(f"Bruins' Historical Record on {today_day_name}s:")
    record_day_df = pd.DataFrame(record_day, index=[0])
    st.table(record_day_df)
else:
    st.write(f"No historical games found on {today_day_name}s in the selected season range.")

# --- Interactive Exploration ---

st.header("Explore Bruins' Records")

# Select Date or Day of the Week
explore_option = st.radio("Select an option to explore:", ("Specific Date", "Day of the Week"))

if explore_option == "Specific Date":
    # Select Month and Day
    months = list(range(1, 13))
    month_names = [pd.to_datetime(f'{m}', format='%m').strftime('%B') for m in months]
    month_dict = dict(zip(months, month_names))
    selected_month = st.selectbox("Select a month", months, format_func=lambda x: month_dict[x])
    from calendar import monthrange
    year_for_monthrange = 2020  # Leap year to account for February 29
    days_in_month = monthrange(year_for_monthrange, selected_month)[1]
    selected_day = st.selectbox("Select a day", list(range(1, days_in_month + 1)))
    selected_mm_dd = f"{selected_month:02d}-{selected_day:02d}"
    date_str = pd.to_datetime(f"{selected_month}-{selected_day}", format="%m-%d").strftime('%B %d')

    # Option to select opponent
    opponent_list = ['All'] + sorted(df_filtered['Opponent'].unique())
    selected_opponent = st.selectbox("Select an opponent (optional)", opponent_list)
    if selected_opponent == 'All':
        selected_opponent = None

    # Calculate and display record
    record_on_selected_date = calculate_record_on_date(df_filtered, selected_mm_dd, selected_opponent)
    if record_on_selected_date:
        if selected_opponent:
            st.subheader(f"Record against {selected_opponent} on {date_str}:")
        else:
            st.subheader(f"Overall record on {date_str}:")
        record_date_df = pd.DataFrame(record_on_selected_date, index=[0])
        st.table(record_date_df)
    else:
        st.write(f"No games found on {date_str} in the selected season range.")

elif explore_option == "Day of the Week":
    # Select Day of the Week
    days_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    selected_day_name = st.selectbox("Select a day of the week", days_of_week)

    # Option to select opponent
    opponent_list = ['All'] + sorted(df_filtered['Opponent'].unique())
    selected_opponent = st.selectbox("Select an opponent (optional)", opponent_list, key='opponent_day')
    if selected_opponent == 'All':
        selected_opponent = None

    # Calculate and display record
    record_on_selected_day = calculate_record_on_day(df_filtered, selected_day_name, selected_opponent)
    if record_on_selected_day:
        if selected_opponent:
            st.subheader(f"Record against {selected_opponent} on {selected_day_name}s:")
        else:
            st.subheader(f"Overall record on {selected_day_name}s:")
        record_day_df = pd.DataFrame(record_on_selected_day, index=[0])
        st.table(record_day_df)
    else:
        st.write(f"No games found on {selected_day_name}s in the selected season range.")

# --- Best and Worst Day to Play Against a Given Opponent ---
st.header("Best and Worst Day to Play Against an Opponent")

# Select Opponent
opponent_list = sorted(df_filtered['Opponent'].unique())
selected_opponent_for_best_day = st.selectbox("Select an opponent", opponent_list, key='best_day_opponent')

# Calculate and display best and worst day
day_info = best_and_worst_day_against_opponent(df_filtered, selected_opponent_for_best_day)
if day_info:
    (best_day, best_day_stats), (worst_day, worst_day_stats), win_stats_by_day = day_info

    # Prepare best day stats
    best_day_total_games = int(best_day_stats['games_played'])
    best_day_wins = int(best_day_stats['wins'])
    best_day_win_percentage = best_day_stats['Win Percentage (%)']

    # Prepare worst day stats
    worst_day_total_games = int(worst_day_stats['games_played'])
    worst_day_wins = int(worst_day_stats['wins'])
    worst_day_win_percentage = worst_day_stats['Win Percentage (%)']

    # Display best and worst days
    st.subheader(f"Best Day to Play Against {selected_opponent_for_best_day}: **{best_day}**")
    st.markdown(f"- Total Games: **{best_day_total_games}**")
    st.markdown(f"- Wins: **{best_day_wins}**")
    st.markdown(f"- Win Percentage: **{best_day_win_percentage}%**")

    st.subheader(f"Worst Day to Play Against {selected_opponent_for_best_day}: **{worst_day}**")
    st.markdown(f"- Total Games: **{worst_day_total_games}**")
    st.markdown(f"- Wins: **{worst_day_wins}**")
    st.markdown(f"- Win Percentage: **{worst_day_win_percentage}%**")

    # Display detailed stats by day
    st.write("Win Percentage by Day of the Week:")
    win_stats_by_day_display = win_stats_by_day.reset_index()
    win_stats_by_day_display = win_stats_by_day_display.dropna(subset=['games_played'])
    st.table(win_stats_by_day_display)
else:
    st.write(f"No games found against {selected_opponent_for_best_day} in the selected season range.")

# --- Detailed Performance Against an Opponent ---
st.header("Detailed Performance Against an Opponent")

selected_opponent = st.selectbox("Select an opponent to view detailed stats", opponent_list, key='detailed_opponent')

opponent_games = df_filtered[df_filtered['Opponent'] == selected_opponent]
if not opponent_games.empty:
    total_games = len(opponent_games)
    wins = int(opponent_games['Win'].sum())
    losses = int(len(opponent_games[opponent_games['Outcome'].str.contains('Loss')]))
    ties = int(len(opponent_games[opponent_games['Outcome'] == 'Tie']))
    win_percentage = round((wins / total_games) * 100, 2)

    record_opponent = {
        'Total Games': total_games,
        'Wins': wins,
        'Losses': losses,
        'Ties': ties,
        'Win Percentage (%)': win_percentage
    }
    st.subheader(f"Record against {selected_opponent}:")
    record_opponent_df = pd.DataFrame(record_opponent, index=[0])
    st.table(record_opponent_df)

    # Display last 5 games against the selected opponent
    st.subheader(f"Last 5 games against {selected_opponent}:")
    st.dataframe(opponent_games.sort_values('Date', ascending=False).head(5)[['Date', 'Location', 'Outcome', 'GF', 'GA']])
else:
    st.write(f"No games found against {selected_opponent} in the selected season range.")

# --- Performance Against All Teams ---
st.header("Performance Against All Teams")

# Prepare data
team_performance = df_filtered.groupby('Opponent')['Win'].mean().reset_index()
team_performance = team_performance.rename(columns={'Win': 'Win Percentage'})
team_performance['Win Percentage'] = team_performance['Win Percentage'] * 100  # Convert to percentage

# Create an interactive Plotly bar chart with black border around the Bruins Gold bars
fig2 = go.Figure(go.Bar(
    x=team_performance['Opponent'],
    y=team_performance['Win Percentage'],
    marker=dict(
        color=bruins_gold,
        line=dict(color=black_color, width=1)  # Add black border
    ),
    hovertemplate='Opponent: %{x}<br>Win Percentage: %{y:.2f}%<extra></extra>'
))

fig2.update_layout(
    plot_bgcolor=background_color,
    paper_bgcolor=background_color,
    font_color=text_color,
    xaxis_title='Opponent',
    yaxis_title='Win Percentage',
    title='Win Percentage Against All Teams',
    xaxis_tickangle=45,
    legend_title_text='',
)
st.plotly_chart(fig2, use_container_width=True)

st.write("Data provided by [Hockey-Reference.com](https://www.hockey-reference.com/teams/BOS/2021_games.html)")
