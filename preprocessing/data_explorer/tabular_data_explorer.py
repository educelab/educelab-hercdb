def investigate_metadata_column(df, column_name, non_papryus_only=False):
    '''
    Given a column name, it will find non-NaN values and print its value along 
    with Papyrus-cornice-pezzo-frag information
    '''

    report = []
    
    filtered_df = df.dropna(subset=[column_name])
    for _, row in filtered_df.iterrows():
        papyrus_n = row['PapyrusNum']
        cornice = row['CorniceNum']
        pezzo = row['Pezzo']
        disegni = row['Disegni']
        col_val = row[column_name]
            
        if non_papryus_only:
            # Only append if at least one of cornice, pezzo, or disegni is truthy
            if any([cornice, pezzo, disegni]):
                report.append((papyrus_n, cornice, pezzo, disegni, col_val))
        else:
            # Always append if non_papryus_only is False
            report.append((papyrus_n, cornice, pezzo, disegni, col_val))
        
    return report

def find_pherc_outliers(df, pherc_col):
    results = []
    for _, row in df.iterrows():
        if row[pherc_col]:
            if not row[pherc_col].isdigit():
                results.append((row[pherc_col], row['UUID'])) 
    return results

def find_uuid_assignment(df, requested_cols):
    results = []
    for _, row in df.iterrows():
        row_info = []
        if row['UUID']:
            row_info.append(row['UUID'])
            for col in requested_cols:
                row_info.append(row[col])

        results.append(row_info)

    return results
    
def compare_uuid_assignment(metadata_df, uuid_df):

    uuids = find_uuid_assignment(uuid_df, ['PHerc', 'Pezzo/Cr'])

    # Create a filtered df with those lines that contain UUID
    filtered_meta_df = metadata_df[metadata_df['UUID'].notnull()]

    new_uuids = []
    for _, row in filtered_meta_df.iterrows():
        found = False
        for uuid_info in uuids:
            # Check if the first element of the sublist matches the target
            if uuid_info[0] == row['UUID']:
                uuid_info.extend([row['PapyrusNum'], row['CorniceNum'], row['Pezzo'], row['Disegni']])
                found = True
                break
        if not found:
            print(f"uuid not found: {row['UUID']}")
            new_uuids.append([row['UUID'], None, None, row['PapyrusNum'], 
                              row['CorniceNum'], row['Pezzo'], row['Disegni']])

    uuids.extend(new_uuids)
                             
    return uuids
            
    