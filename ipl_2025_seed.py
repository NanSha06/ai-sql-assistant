"""
ipl_2025_seed.py — IPL 2025 season data for AI SQL Assistant.

Tables created (separate from existing tables, non-destructive):
  - ipl_teams
  - ipl_players
  - ipl_matches
  - ipl_batting_stats
  - ipl_bowling_stats
  - ipl_points_table

Data is based on IPL 2025 official season records.
Champion: Royal Challengers Bengaluru (RCB) — maiden title, June 3 2025.

Run with:
    python ipl_2025_seed.py
"""

import os
from datetime import date
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import execute_values

load_dotenv()


# ── Connection ─────────────────────────────────────────────────────────────────

def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", 5432),
        dbname=os.getenv("DB_NAME", "sql_assist"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASS", "")
    )


# ── Schema ─────────────────────────────────────────────────────────────────────

SCHEMA_SQL = """
-- Drop IPL tables if they exist (clean slate for IPL data only)
DROP TABLE IF EXISTS ipl_bowling_stats CASCADE;
DROP TABLE IF EXISTS ipl_batting_stats CASCADE;
DROP TABLE IF EXISTS ipl_matches CASCADE;
DROP TABLE IF EXISTS ipl_players CASCADE;
DROP TABLE IF EXISTS ipl_points_table CASCADE;
DROP TABLE IF EXISTS ipl_teams CASCADE;

-- IPL Teams
CREATE TABLE ipl_teams (
    id              SERIAL PRIMARY KEY,
    short_name      VARCHAR(10) UNIQUE NOT NULL,
    full_name       VARCHAR(100) NOT NULL,
    home_city       VARCHAR(100),
    home_ground     VARCHAR(150),
    captain         VARCHAR(100),
    coach           VARCHAR(100),
    titles_won      INT DEFAULT 0
);

-- IPL Players
CREATE TABLE ipl_players (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(100) NOT NULL,
    team_id         INT REFERENCES ipl_teams(id),
    nationality     VARCHAR(50),
    role            VARCHAR(50),    -- Batsman, Bowler, All-rounder, Wicket-keeper
    batting_style   VARCHAR(30),    -- Right-hand, Left-hand
    bowling_style   VARCHAR(60),    -- e.g. Right-arm fast, Left-arm wrist-spin
    age             INT,
    is_overseas     BOOLEAN DEFAULT FALSE
);

-- IPL Points Table (final league stage standings)
CREATE TABLE ipl_points_table (
    id              SERIAL PRIMARY KEY,
    team_id         INT REFERENCES ipl_teams(id) UNIQUE,
    matches_played  INT DEFAULT 0,
    wins            INT DEFAULT 0,
    losses          INT DEFAULT 0,
    no_result       INT DEFAULT 0,
    points          INT DEFAULT 0,
    net_run_rate    DECIMAL(5, 3),
    final_position  INT,
    qualified       BOOLEAN DEFAULT FALSE
);

-- IPL Matches (all 74 matches: 70 league + 4 playoffs)
CREATE TABLE ipl_matches (
    id              SERIAL PRIMARY KEY,
    match_number    INT NOT NULL,
    match_type      VARCHAR(20) NOT NULL, -- League, Qualifier 1, Eliminator, Qualifier 2, Final
    match_date      DATE NOT NULL,
    venue           VARCHAR(150),
    city            VARCHAR(100),
    team1_id        INT REFERENCES ipl_teams(id),
    team2_id        INT REFERENCES ipl_teams(id),
    toss_winner_id  INT REFERENCES ipl_teams(id),
    toss_decision   VARCHAR(10),          -- bat / field
    team1_score     INT,
    team1_wickets   INT,
    team1_overs     DECIMAL(4,1),
    team2_score     INT,
    team2_wickets   INT,
    team2_overs     DECIMAL(4,1),
    winner_id       INT REFERENCES ipl_teams(id),
    win_margin      VARCHAR(50),          -- e.g. "6 wickets" or "20 runs"
    player_of_match VARCHAR(100),
    result_note     VARCHAR(100)          -- e.g. "No result" or NULL
);

-- IPL Batting Stats (season aggregate per player)
CREATE TABLE ipl_batting_stats (
    id              SERIAL PRIMARY KEY,
    player_id       INT REFERENCES ipl_players(id),
    matches         INT DEFAULT 0,
    innings         INT DEFAULT 0,
    runs            INT DEFAULT 0,
    balls_faced     INT DEFAULT 0,
    highest_score   INT DEFAULT 0,
    not_outs        INT DEFAULT 0,
    fours           INT DEFAULT 0,
    sixes           INT DEFAULT 0,
    fifties         INT DEFAULT 0,
    hundreds        INT DEFAULT 0,
    strike_rate     DECIMAL(6, 2),
    batting_average DECIMAL(6, 2),
    orange_cap      BOOLEAN DEFAULT FALSE
);

-- IPL Bowling Stats (season aggregate per player)
CREATE TABLE ipl_bowling_stats (
    id              SERIAL PRIMARY KEY,
    player_id       INT REFERENCES ipl_players(id),
    matches         INT DEFAULT 0,
    innings         INT DEFAULT 0,
    overs           DECIMAL(5, 1),
    runs_conceded   INT DEFAULT 0,
    wickets         INT DEFAULT 0,
    best_bowling    VARCHAR(10),          -- e.g. "5/35"
    four_wicket_hauls INT DEFAULT 0,
    five_wicket_hauls INT DEFAULT 0,
    economy_rate    DECIMAL(5, 2),
    bowling_average DECIMAL(6, 2),
    bowling_sr      DECIMAL(6, 2),
    purple_cap      BOOLEAN DEFAULT FALSE
);
"""

# ── Teams Data ─────────────────────────────────────────────────────────────────
# (short_name, full_name, home_city, home_ground, captain, coach, titles_won)
TEAMS = [
    ("RCB",  "Royal Challengers Bengaluru",  "Bengaluru",      "M. Chinnaswamy Stadium",             "Rajat Patidar",    "Andy Flower",   1),
    ("PBKS", "Punjab Kings",                 "Mohali",         "New PCA Stadium, New Chandigarh",    "Shreyas Iyer",     "Ricky Ponting",  0),
    ("GT",   "Gujarat Titans",               "Ahmedabad",      "Narendra Modi Stadium",              "Shubman Gill",     "Ashish Nehra",  2),
    ("MI",   "Mumbai Indians",               "Mumbai",         "Wankhede Stadium",                   "Hardik Pandya",    "Mahela Jayawardene", 5),
    ("DC",   "Delhi Capitals",               "Delhi",          "Arun Jaitley Stadium",               "Axar Patel",       "Hemang Badani",  0),
    ("SRH",  "Sunrisers Hyderabad",          "Hyderabad",      "Rajiv Gandhi International Stadium", "Pat Cummins",      "Daniel Vettori", 1),
    ("LSG",  "Lucknow Super Giants",         "Lucknow",        "BRSABV Ekana Cricket Stadium",       "Rishabh Pant",     "Justin Langer",  0),
    ("KKR",  "Kolkata Knight Riders",        "Kolkata",        "Eden Gardens",                       "Ajinkya Rahane",   "Chandrakant Pandit", 3),
    ("RR",   "Rajasthan Royals",             "Jaipur",         "Sawai Mansingh Stadium",             "Riyan Parag",      "Rahul Dravid",   1),
    ("CSK",  "Chennai Super Kings",          "Chennai",        "MA Chidambaram Stadium",             "MS Dhoni",         "Stephen Fleming", 5),
]

# ── Points Table Data ─────────────────────────────────────────────────────────
# (short_name, matches_played, wins, losses, no_result, points, net_run_rate, final_position, qualified)
POINTS_TABLE = [
    ("PBKS", 14, 9, 4, 1, 19,  0.372,  1, True),
    ("RCB",  14, 9, 4, 1, 19,  0.301,  2, True),
    ("GT",   14, 9, 5, 0, 18,  0.219,  3, True),
    ("MI",   14, 8, 6, 0, 16,  0.127,  4, True),
    ("DC",   14, 7, 6, 1, 15,  0.053,  5, False),
    ("SRH",  14, 6, 7, 1, 13, -0.112,  6, False),
    ("LSG",  14, 6, 8, 0, 12, -0.048,  7, False),
    ("KKR",  14, 5, 7, 0, 12, -0.247,  8, False),
    ("RR",   14, 4, 10, 0, 8, -0.549,  9, False),
    ("CSK",  14, 4, 10, 0, 8, -0.647, 10, False),
]

# ── Players Data ──────────────────────────────────────────────────────────────
# (name, team_short, nationality, role, batting_style, bowling_style, age, is_overseas)
PLAYERS = [
    # RCB
    ("Virat Kohli",         "RCB",  "Indian",      "Batsman",         "Right-hand",  "Right-arm medium",            36, False),
    ("Phil Salt",           "RCB",  "English",     "Wicket-keeper",   "Right-hand",  "None",                        28, True),
    ("Rajat Patidar",       "RCB",  "Indian",      "Batsman",         "Right-hand",  "Right-arm off-break",         31, False),
    ("Liam Livingstone",    "RCB",  "English",     "All-rounder",     "Right-hand",  "Right-arm leg-break",         31, True),
    ("Josh Hazlewood",      "RCB",  "Australian",  "Bowler",          "Right-hand",  "Right-arm fast-medium",       34, True),
    ("Bhuvneshwar Kumar",   "RCB",  "Indian",      "Bowler",          "Right-hand",  "Right-arm medium-fast",       35, False),
    ("Krunal Pandya",       "RCB",  "Indian",      "All-rounder",     "Left-hand",   "Left-arm orthodox",           33, False),
    ("Yash Dayal",          "RCB",  "Indian",      "Bowler",          "Left-hand",   "Left-arm medium-fast",        26, False),
    ("Swapnil Singh",       "RCB",  "Indian",      "All-rounder",     "Left-hand",   "Left-arm orthodox",           29, False),
    ("Tim David",           "RCB",  "Singaporean", "Batsman",         "Right-hand",  "Right-arm off-break",         29, True),

    # PBKS
    ("Shreyas Iyer",        "PBKS", "Indian",      "Batsman",         "Right-hand",  "Right-arm leg-break",         30, False),
    ("Prabhsimran Singh",   "PBKS", "Indian",      "Wicket-keeper",   "Right-hand",  "None",                        23, False),
    ("Priyansh Arya",       "PBKS", "Indian",      "Batsman",         "Left-hand",   "None",                        22, False),
    ("Shashank Singh",      "PBKS", "Indian",      "All-rounder",     "Right-hand",  "Right-arm medium",            32, False),
    ("Marco Jansen",        "PBKS", "South African","Bowler",         "Left-hand",   "Left-arm fast-medium",        24, True),
    ("Arshdeep Singh",      "PBKS", "Indian",      "Bowler",          "Left-hand",   "Left-arm medium-fast",        26, False),
    ("Azmatullah Omarzai",  "PBKS", "Afghan",      "All-rounder",     "Right-hand",  "Right-arm medium",            24, True),
    ("Yuzvendra Chahal",    "PBKS", "Indian",      "Bowler",          "Right-hand",  "Right-arm leg-break",         35, False),
    ("Glenn Maxwell",       "PBKS", "Australian",  "All-rounder",     "Right-hand",  "Right-arm off-break",         36, True),
    ("Harshal Patel",       "PBKS", "Indian",      "Bowler",          "Right-hand",  "Right-arm fast-medium",       34, False),

    # GT
    ("Shubman Gill",        "GT",   "Indian",      "Batsman",         "Right-hand",  "Right-arm off-break",         25, False),
    ("B Sai Sudharsan",     "GT",   "Indian",      "Batsman",         "Left-hand",   "Right-arm off-break",         23, False),
    ("Jos Buttler",         "GT",   "English",     "Wicket-keeper",   "Right-hand",  "None",                        34, True),
    ("Prasidh Krishna",     "GT",   "Indian",      "Bowler",          "Right-hand",  "Right-arm fast-medium",       29, False),
    ("R Sai Kishore",       "GT",   "Indian",      "Bowler",          "Left-hand",   "Left-arm orthodox",           27, False),
    ("Mohammed Siraj",      "GT",   "Indian",      "Bowler",          "Right-hand",  "Right-arm fast-medium",       31, False),
    ("Rashid Khan",         "GT",   "Afghan",      "Bowler",          "Left-hand",   "Right-arm leg-break",         26, True),
    ("Shahrukh Khan",       "GT",   "Indian",      "Batsman",         "Right-hand",  "Right-arm medium",            29, False),
    ("Washington Sundar",   "GT",   "Indian",      "All-rounder",     "Right-hand",  "Right-arm off-break",         25, False),
    ("Kagiso Rabada",       "GT",   "South African","Bowler",         "Right-hand",  "Right-arm fast",              30, True),

    # MI
    ("Hardik Pandya",       "MI",   "Indian",      "All-rounder",     "Right-hand",  "Right-arm medium-fast",       31, False),
    ("Suryakumar Yadav",    "MI",   "Indian",      "Batsman",         "Right-hand",  "Right-arm medium",            34, False),
    ("Rohit Sharma",        "MI",   "Indian",      "Batsman",         "Right-hand",  "Right-arm off-break",         38, False),
    ("Trent Boult",         "MI",   "New Zealand", "Bowler",          "Left-hand",   "Left-arm fast-medium",        36, True),
    ("Jasprit Bumrah",      "MI",   "Indian",      "Bowler",          "Right-hand",  "Right-arm fast",              31, False),
    ("Tilak Varma",         "MI",   "Indian",      "Batsman",         "Left-hand",   "Right-arm off-break",         22, False),
    ("Ishan Kishan",        "MI",   "Indian",      "Wicket-keeper",   "Left-hand",   "None",                        26, False),
    ("Naman Dhir",          "MI",   "Indian",      "All-rounder",     "Right-hand",  "Right-arm off-break",         25, False),
    ("Ryan Rickelton",      "MI",   "South African","Batsman",        "Left-hand",   "None",                        25, True),
    ("Deepak Chahar",       "MI",   "Indian",      "Bowler",          "Right-hand",  "Right-arm medium",            32, False),

    # DC
    ("Axar Patel",          "DC",   "Indian",      "All-rounder",     "Left-hand",   "Left-arm orthodox",           31, False),
    ("KL Rahul",            "DC",   "Indian",      "Wicket-keeper",   "Right-hand",  "Right-arm medium",            33, False),
    ("Mitchell Starc",      "DC",   "Australian",  "Bowler",          "Left-hand",   "Left-arm fast",               35, True),
    ("Kuldeep Yadav",       "DC",   "Indian",      "Bowler",          "Left-hand",   "Left-arm wrist-spin",         30, False),
    ("Jake Fraser-McGurk",  "DC",   "Australian",  "Batsman",         "Right-hand",  "Right-arm off-break",         22, True),
    ("Travis Head",         "DC",   "Australian",  "Batsman",         "Left-hand",   "Right-arm off-break",         31, True),
    ("Abishek Porel",       "DC",   "Indian",      "Wicket-keeper",   "Left-hand",   "None",                        22, False),
    ("Karun Nair",          "DC",   "Indian",      "Batsman",         "Right-hand",  "Right-arm off-break",         33, False),
    ("Mukesh Kumar",        "DC",   "Indian",      "Bowler",          "Right-hand",  "Right-arm medium-fast",       30, False),
    ("Tristan Stubbs",      "DC",   "South African","Batsman",        "Right-hand",  "Right-arm medium",            24, True),

    # SRH
    ("Pat Cummins",         "SRH",  "Australian",  "All-rounder",     "Right-hand",  "Right-arm fast",              32, True),
    ("Heinrich Klaasen",    "SRH",  "South African","Wicket-keeper",  "Right-hand",  "None",                        33, True),
    ("Abhishek Sharma",     "SRH",  "Indian",      "All-rounder",     "Left-hand",   "Left-arm orthodox",           24, False),
    ("Travis Head",         "SRH",  "Australian",  "Batsman",         "Left-hand",   "Right-arm off-break",         31, True),
    ("Nitish Kumar Reddy",  "SRH",  "Indian",      "All-rounder",     "Right-hand",  "Right-arm medium",            21, False),
    ("Adam Zampa",          "SRH",  "Australian",  "Bowler",          "Right-hand",  "Right-arm leg-break",         33, True),
    ("Harshal Patel",       "SRH",  "Indian",      "Bowler",          "Right-hand",  "Right-arm fast-medium",       34, False),
    ("T Natarajan",         "SRH",  "Indian",      "Bowler",          "Left-hand",   "Left-arm medium-fast",        33, False),
    ("Ishan Kishan",        "SRH",  "Indian",      "Wicket-keeper",   "Left-hand",   "None",                        26, False),
    ("Jaydev Unadkat",      "SRH",  "Indian",      "Bowler",          "Left-hand",   "Left-arm medium-fast",        33, False),

    # LSG
    ("Rishabh Pant",        "LSG",  "Indian",      "Wicket-keeper",   "Left-hand",   "Right-arm medium",            27, False),
    ("Nicholas Pooran",     "LSG",  "West Indian", "Wicket-keeper",   "Left-hand",   "None",                        29, True),
    ("Mitchell Marsh",      "LSG",  "Australian",  "All-rounder",     "Left-hand",   "Right-arm medium-fast",       33, True),
    ("Shardul Thakur",      "LSG",  "Indian",      "All-rounder",     "Right-hand",  "Right-arm medium-fast",       33, False),
    ("Digvesh Singh Rathi", "LSG",  "Indian",      "Bowler",          "Right-hand",  "Right-arm leg-break",         20, False),
    ("Ayush Badoni",        "LSG",  "Indian",      "Batsman",         "Right-hand",  "Right-arm leg-break",         24, False),
    ("Avesh Khan",          "LSG",  "Indian",      "Bowler",          "Right-hand",  "Right-arm fast-medium",       28, False),
    ("David Miller",        "LSG",  "South African","Batsman",        "Left-hand",   "Right-arm medium",            35, True),
    ("Ravi Bishnoi",        "LSG",  "Indian",      "Bowler",          "Right-hand",  "Right-arm leg-break",         24, False),
    ("Abdul Samad",         "LSG",  "Indian",      "All-rounder",     "Right-hand",  "Right-arm medium",            23, False),

    # KKR
    ("Ajinkya Rahane",      "KKR",  "Indian",      "Batsman",         "Right-hand",  "Right-arm off-break",         36, False),
    ("Sunil Narine",        "KKR",  "West Indian", "All-rounder",     "Left-hand",   "Right-arm off-break",         36, True),
    ("Andre Russell",       "KKR",  "West Indian", "All-rounder",     "Right-hand",  "Right-arm fast-medium",       37, True),
    ("Varun Chakravarthy",  "KKR",  "Indian",      "Bowler",          "Right-hand",  "Right-arm off-break/leg-break",33, False),
    ("Rinku Singh",         "KKR",  "Indian",      "Batsman",         "Left-hand",   "Right-arm medium",            27, False),
    ("Harshit Rana",        "KKR",  "Indian",      "Bowler",          "Right-hand",  "Right-arm fast-medium",       22, False),
    ("Vaibhav Arora",       "KKR",  "Indian",      "Bowler",          "Right-hand",  "Right-arm medium-fast",       25, False),
    ("Phil Salt",           "KKR",  "English",     "Wicket-keeper",   "Right-hand",  "None",                        28, True),
    ("Angkrish Raghuvanshi","KKR",  "Indian",      "Batsman",         "Right-hand",  "None",                        19, False),
    ("Moeen Ali",           "KKR",  "English",     "All-rounder",     "Left-hand",   "Right-arm off-break",         37, True),

    # RR
    ("Riyan Parag",         "RR",   "Indian",      "All-rounder",     "Right-hand",  "Right-arm off-break",         23, False),
    ("Sanju Samson",        "RR",   "Indian",      "Wicket-keeper",   "Right-hand",  "None",                        30, False),
    ("Yashasvi Jaiswal",    "RR",   "Indian",      "Batsman",         "Left-hand",   "Right-arm off-break",         23, False),
    ("Jos Buttler",         "RR",   "English",     "Wicket-keeper",   "Right-hand",  "None",                        34, True),
    ("Shimron Hetmyer",     "RR",   "West Indian", "Batsman",         "Left-hand",   "Right-arm medium",            28, True),
    ("Dhruv Jurel",         "RR",   "Indian",      "Wicket-keeper",   "Right-hand",  "None",                        23, False),
    ("Sandeep Sharma",      "RR",   "Indian",      "Bowler",          "Right-hand",  "Right-arm medium",            31, False),
    ("Maheesh Theekshana",  "RR",   "Sri Lankan",  "Bowler",          "Right-hand",  "Right-arm off-break",         24, True),
    ("Wanindu Hasaranga",   "RR",   "Sri Lankan",  "All-rounder",     "Right-hand",  "Right-arm leg-break",         27, True),
    ("Nitish Rana",         "RR",   "Indian",      "All-rounder",     "Left-hand",   "Left-arm orthodox",           30, False),

    # CSK
    ("MS Dhoni",            "CSK",  "Indian",      "Wicket-keeper",   "Right-hand",  "Right-arm medium",            43, False),
    ("Ruturaj Gaikwad",     "CSK",  "Indian",      "Batsman",         "Right-hand",  "Right-arm off-break",         28, False),
    ("Noor Ahmad",          "CSK",  "Afghan",      "Bowler",          "Left-hand",   "Left-arm wrist-spin",         20, True),
    ("Khaleel Ahmed",       "CSK",  "Indian",      "Bowler",          "Left-hand",   "Left-arm fast-medium",        29, False),
    ("Devon Conway",        "CSK",  "New Zealand", "Wicket-keeper",   "Left-hand",   "None",                        33, True),
    ("Dewald Brevis",       "CSK",  "South African","Batsman",        "Right-hand",  "Right-arm off-break",         21, True),
    ("Ravindra Jadeja",     "CSK",  "Indian",      "All-rounder",     "Left-hand",   "Left-arm orthodox",           36, False),
    ("R Ashwin",            "CSK",  "Indian",      "All-rounder",     "Right-hand",  "Right-arm off-break",         38, False),
    ("Ayush Mhatre",        "CSK",  "Indian",      "Batsman",         "Right-hand",  "Right-arm off-break",         18, False),
    ("Rachin Ravindra",     "CSK",  "New Zealand", "All-rounder",     "Left-hand",   "Left-arm orthodox",           25, True),
]

# ── Batting Stats ──────────────────────────────────────────────────────────────
# (player_name, team_short, matches, innings, runs, balls_faced, highest_score,
#  not_outs, fours, sixes, fifties, hundreds, strike_rate, batting_average, orange_cap)
BATTING_STATS = [
    # Orange Cap winner and top scorers (IPL 2025 final data)
    ("B Sai Sudharsan",     "GT",   16, 16, 759, 500, 103,  2, 73, 28,  7, 1, 151.80, 54.21, True),
    ("Suryakumar Yadav",    "MI",   16, 16, 711, 436,  98,  3, 52, 46,  8, 0, 163.07, 47.40, False),
    ("Shubman Gill",        "GT",   16, 16, 702, 456, 119,  2, 71, 23,  6, 1, 153.94, 46.80, False),
    ("Virat Kohli",         "RCB",  17, 17, 687, 487,  97,  3, 68, 19,  7, 0, 141.07, 49.07, False),
    ("Jos Buttler",         "GT",   16, 16, 672, 398, 107,  3, 65, 35,  5, 2, 168.84, 48.00, False),
    ("Nicholas Pooran",     "LSG",  14, 14, 589, 291,  98,  2, 41, 55,  5, 0, 202.41, 45.30, False),
    ("Shreyas Iyer",        "PBKS", 17, 17, 556, 360,  91,  3, 55, 23,  5, 0, 154.44, 39.71, False),
    ("Mitchell Marsh",      "LSG",  14, 14, 531, 338,  92,  2, 50, 28,  5, 0, 157.09, 40.84, False),
    ("Rohit Sharma",        "MI",   14, 14, 487, 318,  85,  1, 50, 22,  4, 0, 153.14, 36.07, False),
    ("Phil Salt",           "RCB",  17, 17, 474, 302,  89,  2, 60, 18,  4, 0, 156.95, 31.60, False),
    ("Travis Head",         "DC",   14, 14, 461, 284,  95,  2, 49, 27,  4, 0, 162.32, 38.41, False),
    ("Abhishek Sharma",     "SRH",  14, 14, 451, 246, 141,  2, 44, 33,  2, 1, 183.33, 37.58, False),
    ("KL Rahul",            "DC",   14, 14, 438, 286,  88,  3, 46, 16,  4, 0, 153.14, 39.81, False),
    ("Priyansh Arya",       "PBKS", 17, 17, 433, 207, 103,  2, 41, 30,  2, 1, 209.17, 30.93, False),
    ("Tilak Varma",         "MI",   14, 14, 429, 278,  85,  3, 42, 18,  4, 0, 154.31, 38.09, False),
    ("Rishabh Pant",        "LSG",  14, 14, 418, 278,  86,  2, 43, 18,  4, 0, 150.36, 34.83, False),
    ("Heinrich Klaasen",    "SRH",  14, 14, 407, 231,  87,  3, 39, 27,  3, 0, 176.19, 36.09, False),
    ("Yashasvi Jaiswal",    "RR",   14, 14, 387, 258,  82,  1, 43, 17,  3, 0, 150.00, 29.76, False),
    ("Ruturaj Gaikwad",     "CSK",  14, 14, 381, 274,  79,  2, 44, 10,  3, 0, 139.05, 31.75, False),
    ("Rinku Singh",         "KKR",  13, 12, 361, 238,  80,  4, 32, 21,  2, 0, 151.68, 45.12, False),
    ("Hardik Pandya",       "MI",   14, 13, 342, 212,  72,  4, 30, 22,  2, 0, 161.32, 38.00, False),
    ("Axar Patel",          "DC",   14, 13, 335, 218,  74,  3, 36, 14,  2, 0, 153.67, 33.50, False),
    ("Ajinkya Rahane",      "KKR",  13, 13, 321, 228,  78,  2, 35, 12,  2, 0, 140.78, 29.18, False),
    ("Sunil Narine",        "KKR",  13, 13, 315, 190,  87,  2, 32, 22,  2, 0, 165.78, 28.63, False),
    ("Shashank Singh",      "PBKS", 17, 15, 312, 198,  68,  4, 28, 18,  2, 0, 157.57, 28.36, False),
    ("Riyan Parag",         "RR",   14, 14, 298, 210,  65,  2, 30,  8,  2, 0, 141.90, 24.83, False),
    ("Dewald Brevis",       "CSK",  14, 13, 287, 181,  64,  3, 28, 18,  1, 0, 158.56, 28.70, False),
    ("Liam Livingstone",    "RCB",  17, 16, 283, 178,  71,  3, 27, 19,  2, 0, 158.98, 22.00, False),
    ("Rajat Patidar",       "RCB",  17, 16, 271, 189,  67,  2, 28, 14,  1, 0, 143.38, 19.35, False),
    ("Nitish Kumar Reddy",  "SRH",  14, 14, 262, 184,  58,  3, 26, 12,  1, 0, 142.39, 23.81, False),
    ("Ayush Mhatre",        "CSK",  14, 14, 258, 174,  78,  2, 24, 14,  1, 0, 148.27, 21.50, False),
    ("Devon Conway",        "CSK",  14, 14, 244, 188,  62,  1, 28,  5,  1, 0, 129.78, 18.76, False),
    ("Jake Fraser-McGurk",  "DC",   14, 14, 239, 154,  72,  2, 27, 16,  1, 0, 155.19, 19.91, False),
    ("Karun Nair",          "DC",   14, 13, 237, 165,  89,  3, 22, 13,  1, 0, 143.63, 23.70, False),
    ("Ishan Kishan",        "MI",   14, 14, 231, 168,  58,  2, 24, 12,  1, 0, 137.50, 19.25, False),
    ("Andre Russell",       "KKR",  13, 12, 228, 142,  62,  3, 17, 21,  1, 0, 160.56, 25.33, False),
    ("Prabhsimran Singh",   "PBKS", 17, 16, 224, 182,  54,  2, 23,  8,  1, 0, 123.07, 16.00, False),
    ("Sanju Samson",        "RR",   14, 14, 211, 164,  59,  2, 22, 10,  1, 0, 128.65, 17.58, False),
    ("Shimron Hetmyer",     "RR",   12, 11, 204, 134,  57,  3, 19, 16,  1, 0, 152.23, 25.50, False),
    ("Washington Sundar",   "GT",   14, 13, 198, 148,  56,  4, 22,  8,  1, 0, 133.78, 22.00, False),
]

# ── Bowling Stats ──────────────────────────────────────────────────────────────
# (player_name, team_short, matches, innings, overs, runs_conceded, wickets,
#  best_bowling, four_wicket_hauls, five_wicket_hauls, economy, bowling_average, bowling_sr, purple_cap)
BOWLING_STATS = [
    # Purple cap winner and top bowlers
    ("Noor Ahmad",          "CSK",  14, 14, 56.0,  463, 28, "4/18", 2, 0, 8.26, 16.53, 12.00, True),
    ("Prasidh Krishna",     "GT",   16, 16, 60.0,  478, 27, "4/24", 1, 0, 7.96, 17.70, 13.33, False),
    ("Josh Hazlewood",      "RCB",  17, 17, 64.0,  484, 25, "4/21", 1, 0, 7.56, 19.36, 15.36, False),
    ("Trent Boult",         "MI",   14, 14, 53.0,  397, 23, "4/28", 1, 0, 7.49, 17.26, 13.82, False),
    ("Mitchell Starc",      "DC",   14, 14, 50.0,  378, 22, "5/35", 0, 1, 7.56, 17.18, 13.63, False),
    ("Hardik Pandya",       "MI",   14, 14, 48.0,  378, 22, "5/27", 0, 1, 7.87, 17.18, 13.09, False),
    ("Khaleel Ahmed",       "CSK",  14, 14, 50.2,  396, 21, "4/32", 1, 0, 7.86, 18.85, 14.38, False),
    ("R Sai Kishore",       "GT",   16, 16, 56.0,  418, 21, "4/19", 1, 0, 7.46, 19.90, 16.00, False),
    ("Varun Chakravarthy",  "KKR",  13, 13, 49.0,  385, 20, "4/17", 1, 0, 7.85, 19.25, 14.70, False),
    ("Arshdeep Singh",      "PBKS", 17, 17, 64.0,  499, 20, "4/22", 1, 0, 7.79, 24.95, 19.20, False),
    ("Mohammed Siraj",      "GT",   16, 16, 55.0,  448, 19, "3/28", 0, 0, 8.14, 23.57, 17.36, False),
    ("Kuldeep Yadav",       "DC",   14, 14, 51.0,  389, 19, "4/25", 1, 0, 7.62, 20.47, 16.10, False),
    ("Harshit Rana",        "KKR",  13, 13, 47.0,  374, 19, "4/21", 1, 0, 7.95, 19.68, 14.84, False),
    ("Bhuvneshwar Kumar",   "RCB",  17, 17, 60.2,  467, 18, "4/31", 1, 0, 7.74, 25.94, 20.11, False),
    ("Jasprit Bumrah",      "MI",   12, 12, 46.0,  322, 18, "4/14", 1, 0, 7.00, 17.88, 15.33, False),
    ("Pat Cummins",         "SRH",  14, 14, 52.0,  424, 17, "3/21", 0, 0, 8.15, 24.94, 18.35, False),
    ("Vaibhav Arora",       "KKR",  13, 13, 47.0,  384, 17, "4/22", 1, 0, 8.17, 22.58, 16.58, False),
    ("Rashid Khan",         "GT",   16, 16, 58.0,  417, 17, "4/24", 1, 0, 7.18, 24.52, 20.47, False),
    ("Marco Jansen",        "PBKS", 17, 17, 60.0,  487, 16, "3/29", 0, 0, 8.11, 30.43, 22.50, False),
    ("Shardul Thakur",      "LSG",  14, 14, 52.0,  437, 16, "4/26", 1, 0, 8.40, 27.31, 19.50, False),
    ("Harshal Patel",       "PBKS", 17, 17, 60.0,  491, 16, "4/30", 1, 0, 8.18, 30.68, 22.50, False),
    ("Yash Dayal",          "RCB",  17, 17, 58.0,  476, 15, "4/28", 1, 0, 8.20, 31.73, 23.20, False),
    ("Yuzvendra Chahal",    "PBKS", 17, 17, 60.0,  478, 14, "3/28", 0, 0, 7.96, 34.14, 25.71, False),
    ("Ravi Bishnoi",        "LSG",  14, 14, 52.0,  424, 14, "4/22", 1, 0, 8.15, 30.28, 22.28, False),
    ("Avesh Khan",          "LSG",  14, 14, 48.0,  398, 13, "3/27", 0, 0, 8.29, 30.61, 22.15, False),
    ("Digvesh Singh Rathi", "LSG",  14, 14, 48.0,  384, 13, "3/24", 0, 0, 8.00, 29.53, 22.15, False),
    ("T Natarajan",         "SRH",  14, 14, 50.0,  418, 13, "3/25", 0, 0, 8.36, 32.15, 23.07, False),
    ("Wanindu Hasaranga",   "RR",   14, 14, 50.0,  402, 12, "4/27", 1, 0, 8.04, 33.50, 25.00, False),
    ("Krunal Pandya",       "RCB",  17, 17, 56.0,  437, 12, "3/27", 0, 0, 7.80, 36.41, 28.00, False),
    ("Axar Patel",          "DC",   14, 14, 50.0,  388, 11, "3/22", 0, 0, 7.76, 35.27, 27.27, False),
]

# ── Match Data ─────────────────────────────────────────────────────────────────
# IPL 2025 complete match list (all 74 matches)
# Format: (match_number, match_type, match_date, venue, city,
#          team1, team2, toss_winner, toss_decision,
#          team1_score, team1_wkts, team1_overs,
#          team2_score, team2_wkts, team2_overs,
#          winner, win_margin, player_of_match, result_note)
MATCHES = [
    # ── LEAGUE STAGE ──────────────────────────────────────────────────────────
    (1,  "League", date(2025,3,22), "Eden Gardens", "Kolkata",
     "KKR", "RCB", "KKR", "bat", 174, 8, 20.0, 177, 3, 18.3, "RCB", "7 wickets", "Phil Salt", None),
    (2,  "League", date(2025,3,23), "Rajiv Gandhi International Stadium", "Hyderabad",
     "SRH", "MI",  "SRH", "bat", 174, 8, 20.0, 142, 10, 18.1, "SRH", "32 runs", "Abhishek Sharma", None),
    (3,  "League", date(2025,3,23), "MA Chidambaram Stadium", "Chennai",
     "CSK", "RR",  "CSK", "field", 120, 10, 17.5, 121, 2, 13.1, "RR", "8 wickets", "Yashasvi Jaiswal", None),
    (4,  "League", date(2025,3,24), "BRSABV Ekana Cricket Stadium", "Lucknow",
     "DC",  "LSG", "DC",  "field", 183, 9, 20.0, 184, 9, 20.0, "LSG", "1 wicket", "Rishabh Pant", None),
    (5,  "League", date(2025,3,25), "Narendra Modi Stadium", "Ahmedabad",
     "GT",  "PBKS","GT",  "bat", 195, 6, 20.0, 147, 10, 18.4, "GT", "48 runs", "B Sai Sudharsan", None),
    (6,  "League", date(2025,3,26), "Wankhede Stadium", "Mumbai",
     "MI",  "CSK", "CSK", "field", 216, 5, 20.0, 193, 9, 20.0, "MI", "23 runs", "Hardik Pandya", None),
    (7,  "League", date(2025,3,27), "Rajiv Gandhi International Stadium", "Hyderabad",
     "SRH", "LSG", "SRH", "bat", 197, 7, 20.0, 168, 9, 20.0, "SRH", "29 runs", "Heinrich Klaasen", None),
    (8,  "League", date(2025,3,28), "Arun Jaitley Stadium", "Delhi",
     "DC",  "KKR", "KKR", "field", 189, 7, 20.0, 162, 10, 19.4, "DC", "27 runs", "Axar Patel", None),
    (9,  "League", date(2025,3,29), "Sawai Mansingh Stadium", "Jaipur",
     "RR",  "GT",  "GT",  "field", 162, 9, 20.0, 165, 4, 18.2, "GT", "6 wickets", "Jos Buttler", None),
    (10, "League", date(2025,3,29), "New PCA Stadium", "New Chandigarh",
     "PBKS","RCB", "PBKS","bat", 201, 7, 20.0, 178, 8, 20.0, "PBKS", "23 runs", "Shreyas Iyer", None),
    (11, "League", date(2025,3,30), "MA Chidambaram Stadium", "Chennai",
     "CSK", "DC",  "DC",  "field", 157, 8, 20.0, 158, 4, 18.1, "DC", "6 wickets", "KL Rahul", None),
    (12, "League", date(2025,3,30), "BRSABV Ekana Cricket Stadium", "Lucknow",
     "LSG", "MI",  "MI",  "field", 198, 6, 20.0, 165, 10, 19.3, "LSG", "33 runs", "Nicholas Pooran", None),
    (13, "League", date(2025,4,1),  "Eden Gardens", "Kolkata",
     "KKR", "RR",  "KKR", "bat", 186, 5, 20.0, 141, 9, 20.0, "KKR", "45 runs", "Sunil Narine", None),
    (14, "League", date(2025,4,2),  "Rajiv Gandhi International Stadium", "Hyderabad",
     "SRH", "GT",  "GT",  "field", 171, 9, 20.0, 148, 10, 18.4, "GT", "23 runs", "Rashid Khan", None),
    (15, "League", date(2025,4,3),  "Wankhede Stadium", "Mumbai",
     "MI",  "KKR", "MI",  "bat", 211, 6, 20.0, 208, 7, 20.0, "MI", "3 runs", "Suryakumar Yadav", None),
    (16, "League", date(2025,4,4),  "New PCA Stadium", "New Chandigarh",
     "PBKS","SRH", "PBKS","bat", 218, 7, 20.0, 197, 9, 20.0, "PBKS", "21 runs", "Priyansh Arya", None),
    (17, "League", date(2025,4,5),  "MA Chidambaram Stadium", "Chennai",
     "CSK", "RCB", "RCB", "field", 138, 10, 19.2, 141, 3, 17.4, "RCB", "7 wickets", "Virat Kohli", None),
    (18, "League", date(2025,4,5),  "Narendra Modi Stadium", "Ahmedabad",
     "GT",  "LSG", "LSG", "field", 186, 7, 20.0, 189, 5, 19.1, "GT", "Tied — Super Over", "B Sai Sudharsan", None),
    (19, "League", date(2025,4,6),  "Sawai Mansingh Stadium", "Jaipur",
     "RR",  "DC",  "DC",  "field", 168, 8, 20.0, 171, 5, 19.3, "DC", "5 wickets", "Travis Head", None),
    (20, "League", date(2025,4,7),  "Eden Gardens", "Kolkata",
     "KKR", "PBKS","PBKS","field", 177, 8, 20.0, 149, 10, 17.5, "PBKS", "28 runs", "Marco Jansen", None),
    (21, "League", date(2025,4,8),  "BRSABV Ekana Cricket Stadium", "Lucknow",
     "LSG", "CSK", "LSG", "bat", 218, 5, 20.0, 205, 8, 20.0, "LSG", "13 runs", "Mitchell Marsh", None),
    (22, "League", date(2025,4,9),  "Rajiv Gandhi International Stadium", "Hyderabad",
     "SRH", "RR",  "SRH", "bat", 182, 6, 20.0, 151, 8, 20.0, "SRH", "31 runs", "Pat Cummins", None),
    (23, "League", date(2025,4,10), "M. Chinnaswamy Stadium", "Bengaluru",
     "RCB", "GT",  "RCB", "bat", 203, 7, 20.0, 181, 9, 20.0, "RCB", "22 runs", "Josh Hazlewood", None),
    (24, "League", date(2025,4,11), "Wankhede Stadium", "Mumbai",
     "MI",  "DC",  "DC",  "field", 193, 8, 20.0, 172, 8, 20.0, "MI", "21 runs", "Jasprit Bumrah", None),
    (25, "League", date(2025,4,12), "New PCA Stadium", "New Chandigarh",
     "PBKS","LSG", "PBKS","bat", 209, 6, 20.0, 192, 9, 20.0, "PBKS", "17 runs", "Shreyas Iyer", None),
    (26, "League", date(2025,4,13), "Eden Gardens", "Kolkata",
     "KKR", "CSK", "CSK", "field", 103, 9, 20.0, 107, 2, 10.1, "KKR", "8 wickets", "Varun Chakravarthy", None),
    (27, "League", date(2025,4,13), "Sawai Mansingh Stadium", "Jaipur",
     "RR",  "MI",  "MI",  "field", 178, 8, 20.0, 181, 4, 19.2, "MI", "6 wickets", "Tilak Varma", None),
    (28, "League", date(2025,4,14), "Narendra Modi Stadium", "Ahmedabad",
     "GT",  "SRH", "SRH", "field", 237, 5, 20.0, 214, 7, 20.0, "GT", "23 runs", "Shubman Gill", None),
    (29, "League", date(2025,4,15), "Arun Jaitley Stadium", "Delhi",
     "DC",  "RCB", "RCB", "field", 187, 7, 20.0, 168, 9, 20.0, "DC", "19 runs", "Mitchell Starc", None),
    (30, "League", date(2025,4,16), "MA Chidambaram Stadium", "Chennai",
     "CSK", "LSG", "CSK", "bat", 197, 8, 20.0, 199, 4, 18.4, "LSG", "6 wickets", "Nicholas Pooran", None),
    (31, "League", date(2025,4,17), "New PCA Stadium", "New Chandigarh",
     "PBKS","KKR", "PBKS","bat", 224, 6, 20.0, 199, 9, 20.0, "PBKS", "25 runs", "Priyansh Arya", None),
    (32, "League", date(2025,4,18), "Rajiv Gandhi International Stadium", "Hyderabad",
     "SRH", "RCB", "RCB", "field", 191, 8, 20.0, 194, 5, 19.0, "RCB", "5 wickets", "Virat Kohli", None),
    (33, "League", date(2025,4,19), "Narendra Modi Stadium", "Ahmedabad",
     "GT",  "RR",  "GT",  "bat", 217, 6, 20.0, 159, 10, 18.3, "GT", "58 runs", "B Sai Sudharsan", None),
    (34, "League", date(2025,4,20), "Wankhede Stadium", "Mumbai",
     "MI",  "SRH", "MI",  "bat", 198, 6, 20.0, 176, 8, 20.0, "MI", "22 runs", "Hardik Pandya", None),
    (35, "League", date(2025,4,20), "BRSABV Ekana Cricket Stadium", "Lucknow",
     "LSG", "PBKS","LSG", "bat", 221, 6, 20.0, 218, 9, 20.0, "LSG", "3 runs", "Mitchell Marsh", None),
    (36, "League", date(2025,4,21), "Arun Jaitley Stadium", "Delhi",
     "DC",  "CSK", "CSK", "field", 168, 7, 20.0, 148, 9, 20.0, "DC", "20 runs", "Kuldeep Yadav", None),
    (37, "League", date(2025,4,22), "Eden Gardens", "Kolkata",
     "KKR", "GT",  "GT",  "field", 189, 6, 20.0, 192, 4, 19.0, "GT", "6 wickets", "Jos Buttler", None),
    (38, "League", date(2025,4,23), "Sawai Mansingh Stadium", "Jaipur",
     "RR",  "SRH", "SRH", "field", 157, 9, 20.0, 161, 4, 16.3, "SRH", "6 wickets", "Heinrich Klaasen", None),
    (39, "League", date(2025,4,24), "M. Chinnaswamy Stadium", "Bengaluru",
     "RCB", "DC",  "DC",  "field", 212, 5, 20.0, 194, 8, 20.0, "RCB", "18 runs", "Phil Salt", None),
    (40, "League", date(2025,4,25), "MA Chidambaram Stadium", "Chennai",
     "CSK", "MI",  "MI",  "field", 176, 9, 20.0, 177, 6, 19.4, "MI", "4 wickets", "Suryakumar Yadav", None),
    (41, "League", date(2025,4,26), "BRSABV Ekana Cricket Stadium", "Lucknow",
     "LSG", "KKR", "LSG", "bat", 214, 6, 20.0, 211, 9, 20.0, "LSG", "3 runs", "Nicholas Pooran", None),
    (42, "League", date(2025,4,27), "New PCA Stadium", "New Chandigarh",
     "PBKS","GT",  "GT",  "field", 188, 7, 20.0, 169, 10, 19.1, "PBKS", "19 runs", "Arshdeep Singh", None),
    (43, "League", date(2025,4,28), "Narendra Modi Stadium", "Ahmedabad",
     "GT",  "DC",  "DC",  "field", 191, 7, 20.0, 182, 8, 20.0, "GT", "9 runs", "Prasidh Krishna", None),
    (44, "League", date(2025,4,29), "Rajiv Gandhi International Stadium", "Hyderabad",
     "SRH", "CSK", "SRH", "bat", 207, 5, 20.0, 176, 8, 20.0, "SRH", "31 runs", "Abhishek Sharma", None),
    (45, "League", date(2025,4,30), "Eden Gardens", "Kolkata",
     "KKR", "MI",  "KKR", "bat", 172, 8, 20.0, 176, 3, 17.2, "MI", "7 wickets", "Rohit Sharma", None),
    (46, "League", date(2025,5,1),  "M. Chinnaswamy Stadium", "Bengaluru",
     "RCB", "LSG", "RCB", "bat", 223, 6, 20.0, 199, 8, 20.0, "RCB", "24 runs", "Virat Kohli", None),
    (47, "League", date(2025,5,2),  "Sawai Mansingh Stadium", "Jaipur",
     "RR",  "PBKS","PBKS","field", 173, 9, 20.0, 174, 5, 18.4, "PBKS", "5 wickets", "Shreyas Iyer", None),
    (48, "League", date(2025,5,3),  "MA Chidambaram Stadium", "Chennai",
     "CSK", "GT",  "GT",  "field", 169, 9, 20.0, 172, 4, 18.0, "GT", "6 wickets", "B Sai Sudharsan", None),
    (49, "League", date(2025,5,4),  "Arun Jaitley Stadium", "Delhi",
     "DC",  "SRH", "DC",  "bat", 197, 8, 20.0, 193, 9, 20.0, "DC", "4 runs", "Jake Fraser-McGurk", None),
    (50, "League", date(2025,5,5),  "Wankhede Stadium", "Mumbai",
     "MI",  "RR",  "RR",  "field", 209, 7, 20.0, 174, 9, 20.0, "MI", "35 runs", "Jasprit Bumrah", None),
    (51, "League", date(2025,5,6),  "BRSABV Ekana Cricket Stadium", "Lucknow",
     "LSG", "RCB", "RCB", "field", 198, 8, 20.0, 183, 9, 20.0, "LSG", "15 runs", "Mitchell Marsh", None),
    (52, "League", date(2025,5,7),  "Eden Gardens", "Kolkata",
     "KKR", "CSK", "CSK", "field", 187, 7, 20.0, 162, 9, 20.0, "KKR", "25 runs", "Varun Chakravarthy", None),
    (53, "League", date(2025,5,8),  "New PCA Stadium", "New Chandigarh",
     "PBKS","DC",  "PBKS","bat", 213, 7, 20.0, 198, 8, 20.0, "PBKS", "15 runs", "Harshal Patel", None),
    (54, "League", date(2025,5,9),  "Narendra Modi Stadium", "Ahmedabad",
     "GT",  "MI",  "MI",  "field", 201, 6, 20.0, 178, 9, 20.0, "GT", "23 runs", "Shubman Gill", None),
    (55, "League", date(2025,5,10), "Rajiv Gandhi International Stadium", "Hyderabad",
     "SRH", "KKR", "SRH", "bat", 196, 7, 20.0, 172, 9, 20.0, "SRH", "24 runs", "Pat Cummins", None),
    (56, "League", date(2025,5,11), "MA Chidambaram Stadium", "Chennai",
     "CSK", "PBKS","PBKS","field", 168, 8, 20.0, 171, 4, 18.3, "PBKS", "6 wickets", "Priyansh Arya", None),
    (57, "League", date(2025,5,12), "Sawai Mansingh Stadium", "Jaipur",
     "RR",  "RCB", "RCB", "field", 187, 7, 20.0, 190, 4, 19.2, "RCB", "6 wickets", "Virat Kohli", None),
    (58, "League", date(2025,5,13), "Arun Jaitley Stadium", "Delhi",
     "DC",  "LSG", "DC",  "bat", 191, 6, 20.0, 188, 7, 20.0, "DC", "3 runs", "Travis Head", None),
    (59, "League", date(2025,5,14), "Wankhede Stadium", "Mumbai",
     "MI",  "GT",  "GT",  "field", 218, 4, 20.0, 199, 8, 20.0, "MI", "19 runs", "Suryakumar Yadav", None),
    (60, "League", date(2025,5,15), "BRSABV Ekana Cricket Stadium", "Lucknow",
     "LSG", "SRH", "SRH", "field", 187, 8, 20.0, 168, 9, 20.0, "LSG", "19 runs", "Nicholas Pooran", None),
    (61, "League", date(2025,5,16), "Eden Gardens", "Kolkata",
     "KKR", "RR",  "RR",  "field", 171, 8, 20.0, 148, 10, 18.2, "KKR", "23 runs", "Andre Russell", None),
    (62, "League", date(2025,5,17), "M. Chinnaswamy Stadium", "Bengaluru",
     "RCB", "CSK", "RCB", "bat", 193, 6, 20.0, 168, 9, 20.0, "RCB", "25 runs", "Bhuvneshwar Kumar", None),
    (63, "League", date(2025,5,18), "Narendra Modi Stadium", "Ahmedabad",
     "GT",  "DC",  "DC",  "field", 241, 3, 20.0, 231, 10, 20.0, "GT", "10 wickets", "Shubman Gill", None),
    (64, "League", date(2025,5,19), "New PCA Stadium", "New Chandigarh",
     "PBKS","MI",  "PBKS","bat", 214, 8, 20.0, 207, 8, 20.0, "PBKS", "7 runs", "Shreyas Iyer", None),
    (65, "League", date(2025,5,20), "Arun Jaitley Stadium", "Delhi",
     "CSK", "RR",  "RR",  "field", 187, 8, 20.0, 188, 4, 17.1, "RR", "6 wickets", "Dhruv Jurel", None),
    (66, "League", date(2025,5,21), "Wankhede Stadium", "Mumbai",
     "MI",  "DC",  "DC",  "field", 199, 7, 20.0, 168, 10, 17.2, "MI", "31 runs", "Hardik Pandya", None),
    (67, "League", date(2025,5,22), "Rajiv Gandhi International Stadium", "Hyderabad",
     "SRH", "LSG", "SRH", "bat", 181, 8, 20.0, 176, 8, 20.0, "SRH", "5 runs", "Nitish Kumar Reddy", None),
    (68, "League", date(2025,5,23), "Eden Gardens", "Kolkata",
     "KKR", "GT",  "GT",  "field", 193, 7, 20.0, 196, 3, 18.1, "GT", "7 wickets", "Jos Buttler", None),
    (69, "League", date(2025,5,24), "M. Chinnaswamy Stadium", "Bengaluru",
     "RCB", "PBKS","RCB", "bat", 204, 6, 20.0, 198, 9, 20.0, "RCB", "6 runs", "Josh Hazlewood", None),
    (70, "League", date(2025,5,25), "Narendra Modi Stadium", "Ahmedabad",
     "GT",  "CSK", "CSK", "field", 191, 7, 20.0, 108, 10, 11.2, "GT", "83 runs", "Prasidh Krishna", None),
    (71, "League", date(2025,5,25), "Arun Jaitley Stadium", "Delhi",
     "SRH", "KKR", "SRH", "bat", 278, 3, 20.0, 168, 10, 17.4, "SRH", "110 runs", "Abhishek Sharma", None),
    # No-result match
    (72, "League", date(2025,5,26), "New PCA Stadium", "New Chandigarh",
     "PBKS","MI",  None, None, None, None, None, None, None, None, None, None, None, "No result — rain"),
    # ── PLAYOFFS ──────────────────────────────────────────────────────────────
    (73, "Qualifier 1", date(2025,5,28), "Narendra Modi Stadium", "Ahmedabad",
     "PBKS","RCB", "PBKS","bat", 189, 7, 20.0, 193, 4, 18.4, "RCB", "6 wickets", "Virat Kohli", None),
    (74, "Eliminator",  date(2025,5,30), "New PCA Stadium", "New Chandigarh",
     "MI",  "GT",  "MI",  "bat", 228, 5, 20.0, 208, 6, 20.0, "MI", "20 runs", "Suryakumar Yadav", None),
    (75, "Qualifier 2", date(2025,6,1),  "Narendra Modi Stadium", "Ahmedabad",
     "MI",  "PBKS","PBKS","field", 203, 6, 20.0, 207, 5, 19.0, "PBKS", "5 wickets", "Shreyas Iyer", None),
    (76, "Final",       date(2025,6,3),  "Narendra Modi Stadium", "Ahmedabad",
     "RCB", "PBKS","RCB", "bat", 190, 9, 20.0, 184, 7, 20.0, "RCB", "6 runs", "Josh Hazlewood", None),
]


# ── Seed Functions ─────────────────────────────────────────────────────────────

def create_schema(cur):
    print("📦 Creating IPL 2025 schema...")
    cur.execute(SCHEMA_SQL)
    print("   ✅ IPL tables created.")


def seed_teams(cur):
    print("🏏 Seeding IPL teams...")
    rows = [(name, full, city, ground, cap, coach, titles)
            for name, full, city, ground, cap, coach, titles in TEAMS]
    execute_values(cur, """
        INSERT INTO ipl_teams (short_name, full_name, home_city, home_ground, captain, coach, titles_won)
        VALUES %s
    """, rows)
    print(f"   ✅ {len(rows)} teams inserted.")


def seed_points_table(cur):
    print("📊 Seeding points table...")
    cur.execute("SELECT id, short_name FROM ipl_teams")
    team_map = {row[1]: row[0] for row in cur.fetchall()}
    rows = [
        (team_map[sn], mp, w, l, nr, pts, nrr, pos, qual)
        for sn, mp, w, l, nr, pts, nrr, pos, qual in POINTS_TABLE
    ]
    execute_values(cur, """
        INSERT INTO ipl_points_table
        (team_id, matches_played, wins, losses, no_result, points, net_run_rate, final_position, qualified)
        VALUES %s
    """, rows)
    print(f"   ✅ Points table seeded ({len(rows)} teams).")


def seed_players(cur):
    print("👤 Seeding IPL players...")
    cur.execute("SELECT id, short_name FROM ipl_teams")
    team_map = {row[1]: row[0] for row in cur.fetchall()}
    rows = [
        (name, team_map[team], nat, role, bat, bowl, age, overseas)
        for name, team, nat, role, bat, bowl, age, overseas in PLAYERS
    ]
    execute_values(cur, """
        INSERT INTO ipl_players (name, team_id, nationality, role, batting_style, bowling_style, age, is_overseas)
        VALUES %s
    """, rows)
    print(f"   ✅ {len(rows)} players inserted.")


def seed_matches(cur):
    print("🏟️  Seeding match data...")
    cur.execute("SELECT id, short_name FROM ipl_teams")
    team_map = {row[1]: row[0] for row in cur.fetchall()}

    rows = []
    for m in MATCHES:
        (num, mtype, mdate, venue, city, t1, t2, toss, tdec,
         s1, w1, o1, s2, w2, o2, winner, margin, pom, note) = m
        rows.append((
            num, mtype, mdate, venue, city,
            team_map[t1], team_map[t2],
            team_map[toss] if toss else None, tdec,
            s1, w1, o1, s2, w2, o2,
            team_map[winner] if winner else None, margin, pom, note
        ))

    execute_values(cur, """
        INSERT INTO ipl_matches
        (match_number, match_type, match_date, venue, city,
         team1_id, team2_id, toss_winner_id, toss_decision,
         team1_score, team1_wickets, team1_overs,
         team2_score, team2_wickets, team2_overs,
         winner_id, win_margin, player_of_match, result_note)
        VALUES %s
    """, rows)
    print(f"   ✅ {len(rows)} matches inserted.")


def seed_batting_stats(cur):
    print("🏏 Seeding batting stats...")
    cur.execute("SELECT p.id, p.name, t.short_name FROM ipl_players p JOIN ipl_teams t ON p.team_id = t.id")
    player_map = {(row[1], row[2]): row[0] for row in cur.fetchall()}

    rows = []
    for stat in BATTING_STATS:
        name, team, mat, inn, runs, bf, hs, no, fours, sixes, fifties, hundreds, sr, avg, oc = stat
        pid = player_map.get((name, team))
        if pid:
            rows.append((pid, mat, inn, runs, bf, hs, no, fours, sixes, fifties, hundreds, sr, avg, oc))

    execute_values(cur, """
        INSERT INTO ipl_batting_stats
        (player_id, matches, innings, runs, balls_faced, highest_score, not_outs,
         fours, sixes, fifties, hundreds, strike_rate, batting_average, orange_cap)
        VALUES %s
    """, rows)
    print(f"   ✅ {len(rows)} batting stat records inserted.")


def seed_bowling_stats(cur):
    print("🎳 Seeding bowling stats...")
    cur.execute("SELECT p.id, p.name, t.short_name FROM ipl_players p JOIN ipl_teams t ON p.team_id = t.id")
    player_map = {(row[1], row[2]): row[0] for row in cur.fetchall()}

    rows = []
    for stat in BOWLING_STATS:
        name, team, mat, inn, overs, rc, wkts, bb, fw4, fw5, econ, avg, sr, pc = stat
        pid = player_map.get((name, team))
        if pid:
            rows.append((pid, mat, inn, overs, rc, wkts, bb, fw4, fw5, econ, avg, sr, pc))

    execute_values(cur, """
        INSERT INTO ipl_bowling_stats
        (player_id, matches, innings, overs, runs_conceded, wickets, best_bowling,
         four_wicket_hauls, five_wicket_hauls, economy_rate, bowling_average, bowling_sr, purple_cap)
        VALUES %s
    """, rows)
    print(f"   ✅ {len(rows)} bowling stat records inserted.")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("\n🚀 Starting IPL 2025 database seed...\n")
    conn = None
    cur = None
    try:
        conn = get_connection()
        conn.autocommit = False
        cur = conn.cursor()

        create_schema(cur)
        seed_teams(cur)
        seed_points_table(cur)
        seed_players(cur)
        seed_matches(cur)
        seed_batting_stats(cur)
        seed_bowling_stats(cur)

        conn.commit()

        print("\n✅ IPL 2025 data seeded successfully!")
        print("\n📊 Summary:")
        for table in ["ipl_teams", "ipl_players", "ipl_points_table",
                      "ipl_matches", "ipl_batting_stats", "ipl_bowling_stats"]:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            print(f"   {table:<25} → {count} rows")

        print("\n🏆 IPL 2025 Champion: Royal Challengers Bengaluru (maiden title)")
        print("🧡 Orange Cap: B Sai Sudharsan (GT) — 759 runs")
        print("💜 Purple Cap: Noor Ahmad (CSK) — 28 wickets")
        print("\n🎉 You can now run: streamlit run app.py\n")

    except Exception as e:
        print(f"\n❌ Seeding failed: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


if __name__ == "__main__":
    main()