from educelab import hercdb
import csv
from datetime import datetime

def find_newest_spectral_paths(db, pherc, cornice):
    '''
    Input:
        db:educelab.hercdb connection
        pherc (str):
        cornice (str):
    Returns 
        the path (str)
    '''
    datasets = db.find_datasets(hercdb.SpectralRawType, pherc, cornice)
    
    # To deal with name discrepancies 
    if len(datasets) == 0 and cornice == 'Scorze':
        cornice = 'Scorza'
        datasets = db.find_datasets(hercdb.SpectralRawType, pherc, cornice)

    # If any datasets have been found
    if datasets:
        completed_items = [item for item in datasets if item['complete'] == "TRUE"]

        if completed_items:
            newest_complete = max(completed_items,
                        key=lambda x: datetime.strptime(x['date_end'].split(' (UTC)')[0], 
                        '%m/%d/%Y, %H:%M:%S'))
            #entry = [pherc, cornice, newest_complete['path']]
            
            return newest_complete['path']

    return None
    

if __name__ == "__main__":

    hercdb.config.request_required()
    db = hercdb.connect()
    print(f"Connection established: {db}")
    
    input_file_path = 'Spectral.csv'
    output_file_path = 'Spectral_path_3.csv'
    
    results = []
    
    try:
        with open(input_file_path, 'r') as file:
            csv_reader = csv.reader(file)
            
            header = next(csv_reader)
            print(f"Header: {header}")
    
            for row in csv_reader:
                #print(f"Row: {row}")
    
                for i, value in enumerate(row):
                    if i==0:
                        pherc = str(value)
                    elif i==1:
                        cornice = str(value)
    
                dataset_path = find_newest_spectral_paths(db, pherc, cornice)

                results.append([pherc, cornice, dataset_path])

    
    except FileNotFoundError:
        print(f"Error: File not found at '{file_path}'")
    except Exception as e:
        print(f"An error occurred: {e}")
    
    with open(output_file_path, 'w', newline='') as file:
        csvwriter = csv.writer(file)
        
        # Write data rows one by one
        for row in results:
            csvwriter.writerow(row)
    
    
