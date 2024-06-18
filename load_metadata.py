import csv
import config

metadata_file = config.metadata_file

with open(metadata_file, 'r') as metadata:
    csv_reader = csv.DictReader(metadata)
   
    line_count = 0
    for row in csv_reader:
        if line_count > 1000:
            #break
            pass

        else:
            #print(f'{row["PapyrusNum"]}, {row["CorniceNum"]}, {row["Pezzo"]}: {row["UUID"]}')

            if row["Pezzo"]:
                print(f'Pezzo Row: {row["PapyrusNum"]}, {row["CorniceNum"]}, {row["Pezzo"]}: {row["UUID"]}')

            elif  row["Disegni"]:
                print(f'Disegni Row: {row["PapyrusNum"]}, {row["CorniceNum"]}, {row["Disegni"]}: {row["UUID"]}')
        line_count +=1
