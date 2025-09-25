import streamlit as st
import pandas as pd
import numpy as np
import os
from dotenv import load_dotenv
import requests
from requests.auth import HTTPBasicAuth
import lxml
from bs4 import BeautifulSoup
from datetime import datetime

# Load environment variables (useful for local testing)
load_dotenv()
#read environment variables
API_USER = os.getenv("API_USER")
API_PASSWORD = os.getenv("API_PASSWORD")
API_LIVEXY_URL = os.getenv("API_LIVEXY_URL")

def fetch_livexy_data(gameid):
    try:
        url = API_LIVEXY_URL.format(gameid=gameid)
        response = requests.get(url, auth=HTTPBasicAuth(API_USER,API_PASSWORD))

        if response.status_code != 200:
            return None
        else:
            soup = BeautifulSoup(response.content, features='xml')

            home_tag = soup.find('team', attrs={'isHomeTeam': 'true'})
            home_id = int(home_tag.get('teamId'))
            home_name = home_tag.get('teamName')

            away_tag = soup.find('team', attrs={'isHomeTeam': 'false'})
            away_id = int(away_tag.get('teamId'))
            away_name = away_tag.get('teamName')

            livexy_data = []
            for team in soup.find_all('team'):
                teamid = team.get('teamId')
                teamname = team.get('teamName')

                first_half = team.find('xandYFeed1stHalf')
                if first_half:
                    for stat in first_half.find_all('stat'):
                        livexy_data.append({'Half': 1, 'TeamId': teamid, 'TeamName': teamname} | stat.attrs)

                second_half = team.find('xandYFeed2ndHalf')
                if second_half:
                    for stat in second_half.find_all('stat'):
                        livexy_data.append({'Half': 2, 'TeamId': teamid, 'TeamName': teamname} | stat.attrs)

                third_half = team.find('xandYFeedExtraTime')
                if third_half:
                    for stat in third_half.find_all('stat'):
                        livexy_data.append({'Half': 3, 'TeamId': teamid, 'TeamName': teamname} | stat.attrs)

                fourth_half = team.find('xandYFeedExtraTime2')
                if fourth_half:
                    for stat in fourth_half.find_all('stat'):
                        livexy_data.append({'Half': 4, 'TeamId': teamid, 'TeamName': teamname} | stat.attrs)

            livexy_raw = pd.DataFrame(livexy_data)
            def safe_to_numeric(col):
                try:
                    return pd.to_numeric(col)
                except (ValueError, TypeError):
                    return col

            livexy_raw = livexy_raw.apply(safe_to_numeric)
            livexy_raw.insert(0, 'GameId', gameid)
            livexy_df = livexy_raw.query("SN == 'Play The Ball'").sort_values(by=['VR'])[['GameId','TeamId','TeamName','Half','SC','TN','SN','GM','PN','NX','NY','T']].copy()
            livexy_df[['NX','NY']] = (livexy_df[['NX','NY']]/10).round(0).astype(int)

            tacklers = livexy_raw.set_index(['GameId','Half','SC','TN','TeamId']).query("SN=='Tackle-Made'")['PN']
            tacklers = tacklers.groupby(['GameId', 'Half', 'SC', 'TN', 'TeamId']).agg(', '.join).reset_index()

            livexy_df = livexy_df.merge(
                tacklers,
                on=['GameId','Half','SC','TN'],
                suffixes=('','_Tacklers')
            ).query('TeamId != TeamId_Tacklers')
            livexy_df = livexy_df.drop(columns=['TeamId_Tacklers']).rename(columns={'PN_Tacklers':'Tacklers'})

            return livexy_df
    except Exception as e:
        return None

# Page config
st.set_page_config(layout="wide", page_title="PTB Assessor")
st.title("PTB Assessor")

gameid = st.number_input("Enter a match ID", step=1, format="%d")

if gameid:
    df = fetch_livexy_data(gameid)



    if df is None:
        st.warning("Couldn't retrieve play the ball data")
    else:
        st.success("Successfully retrieved play the ball data")
        df.insert(9, 'PTB Won', False)
        df.insert(10, 'Body Position', '')

        edited_df = st.data_editor(
            df.reset_index(drop=True),
            column_config={
                "GameId":st.column_config.Column("Game ID",disabled=True),
                "TeamId":st.column_config.Column("Team ID",disabled=True),
                "TeamName":st.column_config.Column("Team Name",disabled=True),
                "Half":st.column_config.Column("Half",disabled=True),
                "SC":st.column_config.Column("Set",disabled=True),
                "TN":st.column_config.Column("Tackle",disabled=True),
                "SN":st.column_config.Column("Stat",disabled=True),
                "GM":st.column_config.Column("Min",disabled=True),
                "PN":st.column_config.Column("Player",disabled=True),
                "Body Position": st.column_config.SelectboxColumn(
                    options=["Front", "Back","Standing"],
                    required=False
                ),
                "NX":st.column_config.Column("Length",disabled=True),
                "NY":st.column_config.Column("Width",disabled=True),
                "T":st.column_config.Column("Time",disabled=True),
                "Tacklers":st.column_config.Column("Tacklers",disabled=True)
            },
            use_container_width = True
        )

        # Create file name with match ID and timestamp
        timestamp = datetime.now().strftime("%d%m%y_%H%M")
        filename = f"ptb_labels_{gameid}_{timestamp}.csv"

        # Download button
        csv = edited_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name=filename,
            mime='text/csv'
        )