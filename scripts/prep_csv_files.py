import csv
import os
import pandas as pd
import logging

from educelab.hercdb import config

COL_MAP = {
    'Meta' : {
        'Papiri' : {
            'Columns' : {
                0: 'Unnamed0',
                1 : 'PapyrusNum',
                2 : 'CorniceNum',
                3 : 'Pezzo',
                4 : 'Disegni',
                5 : 'UnrollingStatus',
                6 : 'UUID',
                7 : 'Support',
                8 : 'PaperboardColor',
                9 : 'PaperboardNotes',
                10 : 'OGStorageNum',
                11 : 'PreviouslyKnownAs',
                12 : 'CurrentlyKnownAs',
                13 : 'SeeAlso',
                14 : 'AlternativeUUID',
                15 : 'CustodialInstitution',
                16 : 'CustodialURI',
                17 : 'CustodialCityCountry',
                18 : 'StorageLocation',
                19 : 'StorageLocationNotUnrolledPortion',
                20 : 'StorageLocationURI',
                21 : 'InventoryNum',
                22 : 'History',
                23 : 'CustodialHistory',
                24 : 'Unnamed1',
                25 : 'ObjectFormat',
                26 : 'ObjectFormatURI',
                27 : 'MaterialType',
                28 : 'MaterialTypeURI',
                29 : 'Diameter',
                30 : 'Height',
                31 : 'Width',
                32 : 'Grams',
                33 : 'Language',
                34 : 'LanguageURI',
                35 : 'IntactStatus',
                36 : 'Unroller',
                37 : 'UnrollerURI',
                38 : 'UnrollingMethod',
                39 : 'UnrolledDate',
                40 : 'UnrolledBeforeDate',
                41 : 'UnrolledAfterDate',
                42 : 'OlsoMethod',
                43 : 'ScorzeMethod',
                44 : 'Note',
                45 : 'PhotographFiles',
                46 : 'Infrared',
                47 : 'OtherPhotographs',
                48 : 'BibliographyLink',
                49 : 'Editions',
                50 : 'FurtherBibliography',
                51 : 'TrismegistosNum', 
                52 : 'TrismegistosURI',
                53 : 'LdabNum',
                54 : 'LdabURI',
                55 : 'DclpURI',
                56 : 'DclpScrollsURI',
                57 : 'Scorze',
                58 : 'Cornici',
                59 : 'CorniciCount',
                60 : 'PezziCount',
                61 : 'FragmentCount',
                62 : 'Author',
                63 : 'LiteraryWork',
                64 : 'Subscriptio',
                65 : 'SubscriptioLocation',
                66 : 'InitialEndTitle',
                67 : 'RectoVersoTitle',
                68 : 'Unnamed2',
                69 : 'Unnamed3',
                70 : 'StoredWithPHercNum',
                71 : 'Engravings',
                72 : 'Transcripts',
                73 : 'LayerStructure',
                74 : 'CavalloScribalStyle',
                75 : 'MultipleHands',
                76 : 'NeapolitanDrawings',
                77 : 'OxonianDrawings',
                78 : 'OtherSameScrollPapyri',
                79 : 'AdditionalNotes'
            }
        }
    }
}



def prep_negatives_data():

    inputFileName = config.negs_file 
    outputFileName = os.path.splitext(inputFileName)[0] + "_mod.csv"

    with open(inputFileName, newline='') as inFile, open(outputFileName, 'w', newline='') as outfile:

        r = csv.reader(inFile)
        w = csv.writer(outfile)
    
        next(r, None)  # skip the first row from the reader, the old header
        # write new header
        w.writerow(['Image_num', 'Negatives_series', 'PHerc', 'cornice', 'UUID', 'storage_loc'])
    
        # copy the rest
        for row in r:
            w.writerow(row)

def prep_pg_data():

    inputFileName = config.pgs_file 
    outputFileName = os.path.splitext(inputFileName)[0] + "_mod.csv"

    with open(inputFileName, newline='') as inFile, open(outputFileName, 'w', newline='') as outfile:

        r = csv.reader(inFile)
        w = csv.writer(outfile)
    
        next(r, None)  # skip the first row from the reader, the old header
        # write new header
        w.writerow(["path","type","uuid","datetime_start","datetime_end","complete","sample_uuid"])
    
        # copy the rest
        for row in r:
            w.writerow(row)


def prep_spectral_data():

    inputFileName = config.spectral_file 
    outputFileName = os.path.splitext(inputFileName)[0] + "_mod.csv"

    with open(inputFileName, newline='') as inFile, open(outputFileName, 'w', newline='') as outfile:

        r = csv.reader(inFile)
        w = csv.writer(outfile)
    
        next(r, None)  # skip the first row from the reader, the old header
        # write new header
        w.writerow(["path","type","uuid", "datetime_start","datetime_end", "complete", "sample_uuid","sample_uuid2"])
    
        # copy the rest
        for row in r:
            w.writerow(row)


def prep_metadata_papyri_data():
    # Assumes the papyrus page/tab has been downloaded from Gdrive as a .csv file 

    inputFileName = config.metadata_file
    outputFileName = os.path.splitext(inputFileName)[0] + "_mod.csv"

    #df = pd.read_excel("meta.xlsx", sheet_name="Papiri")  # Use this if downloaded as an Excel spreadsheet
    df = pd.read_csv(inputFileName)
    

    # Remove the first 6 lines and replace them with the cleaner column names above
    data_df = df.iloc[6:]
    column_names = []
    for i in range(80):
        column_names.append(COL_MAP['Meta']['Papiri']['Columns'][i])    
    data_df.columns = column_names

    logging.debug(f'data shape after column cleasing: {data_df.shape}')


    # Remove completely empty rows and columns

    # Get rid of white space only cells (otherwise they are treated as holding values)
    def replace_spaces_only(cell):
        if isinstance(cell, str) and cell.strip() == '':
            return None  # Replace with None, can be replaced with any value
        return cell
    
    data_df = data_df.map(replace_spaces_only)
    
    # Drop empty rows
    data_df = data_df.dropna(how='all')
    
    # Find empty column
    drop_list = data_df.columns[data_df.isnull().all(0)].to_list()
    drop_list.append('Unnamed0')
    logging.debug(f'dropping columns ... {drop_list}')
    data_df = data_df.drop(columns=drop_list)
    
    # Convert NaN to None
    data_df = data_df.where(pd.notnull(data_df), None)
    
    # reset index so that the first data row will be 0
    data_df.reset_index(drop=True, inplace=True)
    
    # PapyrusNum forward fill
    data_df.loc[:, 'PapyrusNum'] = data_df.loc[:, 'PapyrusNum'].ffill()
    
    
    # If a row contains pezzo, fill in the CorniceNum
    for i in range(data_df.shape[0]):
        pezzo = data_df.at[i,'Pezzo']
    
        if not pd.isna(pezzo):
            data_df.at[i, 'CorniceNum'] = data_df.at[i-1,'CorniceNum']
    
    logging.debug(f'final dataframe shape: {data_df.shape}')

    data_df.to_csv(outputFileName, index=False)


if __name__ == "__main__":
    pass
