""" This module compares two csv files on different values

This module was developed to compare two csv files for different values.

Preparation:
-   Before using this module, ensure that the two csv files have a resonable amount of 
    decimal places (e.g. 2 places after comma), otherwise changes due to difference 
    internal computation accuracy will be highlighted as well

Worflow:
-   This worflow can help to compare two different code versions by comparing the resulting 
    output files. Hence:
    1. Calculate 1.csv file with code1 and 2.csv with code 2.csv
    2. read in 1.csv and 2.csv and compare using this module
    3. analyse output .csv file 

Output:
-   .scv file that contains two values separated with '-->' indidicating the change from 1.csv to 2.csv file
    for example: if in field 'a' the value changed from 1.0 to 2.0, it will be displayed as: 
    1.0 --> 2.0 in the output .csv file

@authors: Felix W

"""

# Imports
import pandas as pd
import numpy as np
import sys

# Read in Files
df1=pd.read_csv('Data/Data Berlin/Output/Berlin_building_lvl_feat_francois_cut.csv')
df2=pd.read_csv('Data/Data Berlin/Output/Berlin_building_lvl_feat_nikola_cut.csv')

# Compare Two files
comparison_values = df1.eq(df2)
comparison_values = comparison_values.reindex(df1.columns, axis=1)
rows,cols=np.where(comparison_values==False)

for item in zip(rows,cols):
    df1.iloc[item[0], item[1]] = '{} --> {}'.format(df1.iloc[item[0], item[1]],df2.iloc[item[0], item[1]])

# Define Output File
df1.to_csv('Data/Data Berlin/Output/Berlin_test_bldg_lvl_diff.csv',index=False,header=True)