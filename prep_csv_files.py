import csv
import os
import config

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


if __name__ == "__main__":
    pass
