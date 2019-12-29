## TAKES IN REPLAY FILES FROM AND GIVES DF ##
import carball
import pandas as pd
import numpy as np
from google.protobuf.json_format import MessageToDict
from tqdm import tqdm
import os

pd.set_option('mode.chained_assignment', None)

OBx = []
OBy = []
OBz = []

class OutofBounds(Exception):
    """Raised when the segment is OB"""
    pass

def x_segment(x):
    if x > 4096 or x < -4096:
        print("x:", x)
        OBx.append(x)
        raise OutofBounds
    seg = -4096
    while(True):
        if x >= seg and x < seg+1024:
            return (seg+(seg+1024))/2
        seg += 1024
        
def y_segment(y):
    seg = -5120
    if y < -5120:
        return -5121 # IN BLUE TEAM GOAL
    elif y > 5120:
        return 5121 # IN ORANGE TEAM GOAL
    while(True):
        if y >= seg and y < seg+1024:
            return (seg+(seg+1024))/2
        seg += 1024
        
def z_segment(z):
    if z > 2044 or z < 0:
        print("z:", z)
        OBz.append(z)
        raise OutofBounds
    seg = 0
    while(True):
        if z >= seg and z < seg+292:
            return (seg+(seg+292))/2
        seg += 292

## converting replays ##
#rootdir = '/home/zach/Files/Nas/Replays'
rootdir = '/home/zach/Files/ReplayModels/ReplayDataProcessing/RANKED_STANDARD/Replays/1400-1600'
for root, dirs, files in os.walk(rootdir):
    for filename in files:
        if not filename.endswith('.replay'):
            print("\n", filename, "not a replay\n")
            continue
        tester = os.path.abspath(os.path.join(root, filename)).replace('.replay', '.csv')
        if os.path.exists(tester):
            print("\n", tester, "exists\n")
            continue
        print("ANALYZING...")
        try:
            analysis_manager = carball.analyze_replay_file(os.path.abspath(os.path.join(root, filename)))
        except Exception as e:
            print("ERROR WITH REPLAY ANALYSIS\n", e)
            continue
        proto_game = analysis_manager.get_protobuf_data()
        df = analysis_manager.get_data_frame()
        dict_game = MessageToDict(proto_game)

        player_team = {}
        best_score = 0
        for i in dict_game['players']:
            # indentifies MVP
            if i['score'] > best_score:
                best_score = i['score']
            if i['isOrange']:
                player_team.update({i['name']: tuple([i['score'], 'orange'])})
            else:
                player_team.update({i['name']: tuple([i['score'], 'blue'])})

        # identifying best player(s)
        ordered_playas = []
        for name, score in player_team.items():
            if score[0] == best_score:
                ordered_playas.append(name)

        playas = list(list(df.columns.levels)[0])
        playas.remove('ball')
        playas.remove('game')

        for playa in playas:
            if playa not in ordered_playas and player_team[playa][1] == player_team[ordered_playas[0]][1]:
                ordered_playas.append(playa)

        for playa in playas:
            if playa not in ordered_playas and player_team[playa][1] != player_team[ordered_playas[0]][1]:
                ordered_playas.append(playa)


        ########################### MAKING SURE EACH LEVEL IS SAME LENGTH
        length = len(df['ball'])
        if length != len(df['game']):
            print("BAD")
        for playa in ordered_playas:
            if len(df[playa]) != length:
                print("BAD")
        ###########################

        ## MAKING NEW SINGLE LEVEL DF FOR TRAINING ##
        ## PLAYER 0, 1, AND 1 ARE HIGHEST SCORING PLAYER'S TEAM WHILE 3, 4, AND 5 ARE ON OPPOSITE TEAM ##
        player_desired = 0

        single_level_df = df[ordered_playas[player_desired]]
        rem_cols = ['rot_x','rot_y','rot_z','vel_x','vel_y','vel_z','ang_vel_x','ang_vel_y',\
                'ang_vel_z','ping','throttle','steer','handbrake','ball_cam','boost','boost_active','jump_active',\
                'double_jump_active','dodge_active','boost_collect']  
        for col in rem_cols:
            if col in single_level_df.columns:
                single_level_df.drop(columns=[col], inplace=True)
        single_level_df.rename(columns={'pos_x': str(player_desired)+'_pos_x', 'pos_y': str(player_desired)+'_pos_y', 'pos_z': str(player_desired)+'_pos_z'}, inplace=True)
        for i, playa in enumerate(ordered_playas):
            if player_desired == i:
                continue
            piece = df[playa]
            rem_cols = ['ping','throttle','steer','handbrake','ball_cam','boost','boost_active','jump_active',\
                    'double_jump_active','dodge_active','boost_collect']
            for col in rem_cols:
                if col in piece.columns:
                    piece.drop(columns=[col], inplace=True)
            piece.rename(columns={'pos_x': str(i)+'_pos_x', 'pos_y': str(i)+'_pos_y', 'pos_z': str(i)+'_pos_z', \
                    'rot_x': str(i)+'_rot_x', 'rot_y': str(i)+'_rot_y', 'rot_z': str(i)+'_rot_z', 'vel_x': str(i)+'_vel_x', \
                    'vel_y': str(i)+'_vel_y', 'vel_z': str(i)+'_vel_z', 'ang_vel_x': str(i)+'_ang_vel_x', 'ang_vel_y': str(i)+'_ang_vel_y', \
                    'ang_vel_z': str(i)+'_ang_vel_z'}, inplace=True)
            single_level_df = single_level_df.join(piece)
            
        ball_data = df['ball']
        ball_data.drop(columns=['hit_team_no'], inplace=True)
        ball_data.rename(columns={'pos_x': 'ball_pos_x', 'pos_y': 'ball_pos_y', 'pos_z': 'ball_pos_z', 'rot_x': 'ball_rot_x', \
                'rot_y': 'ball_rot_y', 'rot_z': 'ball_rot_z', 'vel_x': 'ball_vel_x', 'vel_y': 'ball_vel_y', 'vel_z': 'ball_vel_z', \
                'ang_vel_x': 'ball_ang_vel_x', 'ang_vel_y': 'ball_ang_vel_y', 'ang_vel_z': 'ball_ang_vel_z'}, inplace=True)
        single_level_df = single_level_df.join(ball_data)
        single_level_df['seconds_remaining'] = df['game']['seconds_remaining']

        ## CHECK HOW MANY NAN EXIST ## 
        num_nans = len(single_level_df) - len(single_level_df.dropna())
        single_level_df.dropna(inplace=True)
        single_level_df.reset_index(drop=True, inplace=True)

        ## SPLIT POSITIONING INTO SEGMENTS ##
        ## 8 X SEGMENTS, 10 Y SEGMENTS, 7 Z SEGMENTS
        ## THIS GIVES 1024 (X) BY 1024 (Y) BY 292 (Z) CUBES
         
        print("NORMALIZING...")
        try: 
            for i in tqdm(single_level_df.index):
                single_level_df.at[i, '0_pos_x'] = x_segment(single_level_df.at[i, '0_pos_x'])
                single_level_df.at[i, '0_pos_y'] = y_segment(single_level_df.at[i, '0_pos_y'])
                single_level_df.at[i, '0_pos_z'] = z_segment(single_level_df.at[i, '0_pos_z'])
        except OutofBounds:
            print("OB")
            print(OBx)
            print(OBy)
            print(OBz)
            continue

        csv_name = os.path.abspath(os.path.join(root, filename))
        csv_name = csv_name.replace('.replay', '.csv')
        print("WRITING", csv_name)
        single_level_df.to_csv(csv_name)
