import argparse
import csv
import re
from educelab.hercdb.loader import PhercGraphDatabaseLoader

_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}"
    r"-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


def _is_real_uuid(value: str) -> bool:
    """True iff `value` is shaped like a canonical 8-4-4-4-12 UUID.

    Sentinel strings such as "discarded" or "." in the UUID file's
    `Replacement UUID` column should not flow into add_replacement_EduceLabID.
    """
    return bool(value) and bool(_UUID_RE.fullmatch(value.strip()))

parser = argparse.ArgumentParser(description='Load metadata and UUID data into Neo4j')
parser.add_argument('--metadata', default='input_data/metadata_file.csv',
                    help='Path to metadata CSV file (default: input_data/metadata_file.csv)')
parser.add_argument('--uuid', default='input_data/uuid_file.csv',
                    help='Path to UUID CSV file (default: input_data/uuid_file.csv)')
args = parser.parse_args()

processed_metadata_csv = args.metadata
uuid_csv = args.uuid

loader = PhercGraphDatabaseLoader()
loader.verify_conn()

def is_casetta(name: str) -> bool:
    return bool(name) and 'cass' in name.lower()

def set_properties_from_row(obj_type, ph_name, cornice_name, pezzo_name, disegni_name, row, property_map):
    for csv_key, prop_name in property_map.items():
        value = row.get(csv_key)
        if value and value != "--":
            loader.set_node_property(
                node_type=obj_type,
                property_name=prop_name,
                value=value,
                pherc_display_name=ph_name,
                cornice_display_name=cornice_name,
                pezzo_display_name=pezzo_name,
                disegni_name=disegni_name
            )

# First load the metadata 
with open(processed_metadata_csv, 'r') as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        ph_name = row['PapyrusNum']
        cornice_name = row['CorniceNum']
        pezzo_name = row['Pezzo']
        disegni_name = row['Disegni']
        uuid = row['UUID']

        ############ Add main nodes ############
        if disegni_name:
            # Disegni Row
            loader.add_disegni_node_and_attach(ph_name, disegni_name)
            obj_type = "Disegni"
        
        elif pezzo_name:
            # Pezzo row
            loader.add_pezzo_node_and_attach(uuid, pezzo_name, ph_name, cornice_name)
            obj_type = "Pezzo"

        elif cornice_name:
            # Cornice row
            loader.add_cornice_nodes_and_attach(uuid, ph_name, cornice_name)
            obj_type = "Cornice"

        else:
            # PHerc row (may also be a Casetta — flagged via :Casetta label)
            loader.add_pherc_node(uuid, ph_name, is_casetta=is_casetta(ph_name))
            obj_type = "PHerc"

        ########### Set other properties ###########

        # Main property mapping: CSV column -> Neo4j property
        property_map = {
            'UnrollingStatus': 'unrolling_status',
            'SupportMaterial': 'support_material',
            'PaperboardColor': 'paperboard_color',
            'OGStorageNum': 'og_storage_num',
            'PreviouslyKnownAs': 'previously_known_as',
            'CurrentlyKnownAs': 'currently_known_as',
            'SeeAlsoPHerc': 'see_also_herc',
            'StorageLocation': 'storage_location',
            'StorageLocationNotUnrolledPortion': 'storage_location_not_unrolled_portion',
            'History': 'history',
            'CustodialHistory': 'custodial_history',
            'Diameter': 'diameter',
            'Height': 'height',
            'Width': 'width',
            'Grams': 'weight',
            'UnrolledDate': 'unrolled_date',
            'UnrolledBeforeDate': 'unrolled_before_date',
            'UnrolledAfterDate': 'unrolled_after_date',
            'Scorze1': 'scorze',
            'Note': 'note',
            'PhotographFiles': 'photograph_files',
            'OtherPhotographs': 'other_photographs',
            'BibliographyLink': 'bibliography_link',
            'Editions': 'editions',
            'FurtherBibliography': 'further_bibliography',
            'TrismegistosNum': 'trismegistos_num',
            'TrismegistosURI': 'trismegistos_uri',
            'LdabNum': 'ldab_num',
            'LdabURI': 'ldab_uri',
            'DclpURI': 'dclp_uri',
            'DclpScrollsURI': 'dclp_scrolls_uri',
            'Cornici': 'cornici',
            'CorniciCount': 'cornici_count',
            'LiteraryWork': 'literary_work',
            'Subscriptio': 'subscriptio',
            'SubscriptioLocation': 'subscriptio_location',
            'InitialEndTitle': 'initial_end_title',
            'RectoVersoTitle': 'recto_verso_title',
            'StoredWithPHercNum': 'stored_with_pherc_num',
            'Engravings': 'engravings',
            'Transcripts': 'transcripts',
            'MultipleHands': 'multiple_hands',
            'NeapolitanDrawings': 'neapolitan_drawings',
            'OxonianDrawings': 'oxonian_drawings',
            'OtherSameScrollPapyri': 'other_same_scroll_papyri',
            'AdditionalNotes': 'additional_notes',
        }

        # Set all simple properties
        set_properties_from_row(obj_type, ph_name, cornice_name, pezzo_name, disegni_name, row, property_map)

    
        # Special cases
        if row['CustodialInstitution']:
            loader.add_custodial_institution_node(
                node_type=obj_type,
                pherc_display_name=ph_name,
                institution_name=row['CustodialInstitution'],
                insitution_url=row['CustodialURI'],
                cornice_display_name=cornice_name,
                pezzo_display_name=pezzo_name,
                disegni_name=disegni_name
            )
            # Assumes this will only exist if there is an institution
            if row['CustodialCityCountry']:
                loader.add_custodial_location_node(
                    institution_name=row['CustodialInstitution'],
                    location=row['CustodialCityCountry'],
                    location_url=row['CityCountryURI']
                )

        if row['ObjectFormat']:
            loader.add_object_format_node_and_attach(
                node_type=obj_type,
                pherc_display_name=ph_name,
                object_format=row['ObjectFormat'],
                object_format_url= row['ObjectFormatURI'],
                cornice_display_name=cornice_name,
                pezzo_display_name=pezzo_name,
                disegni_name=disegni_name                
            )
            
        if row['MaterialType']:
            loader.add_material_type_node_and_attach(
                node_type=obj_type,
                pherc_display_name=ph_name,
                material_type=row['MaterialType'],
                material_type_url=row['MaterialTypeURI'],
                cornice_display_name=cornice_name,
                pezzo_display_name=pezzo_name,
                disegni_name=disegni_name               
            )
            
        if row['Language']:
            if row['Language'] in ("grc/lat", "lat/grc"):
                for l in ["grc", "lat"]:
                    loader.add_language_node_and_attach(    
                        language=l,
                        node_type=obj_type,
                        pherc_display_name=ph_name,
                        language_url=row['LanguageURI'],
                        cornice_display_name=cornice_name,
                        pezzo_display_name=pezzo_name,
                        disegni_name=disegni_name
                    )

            elif row['Language'] in ("inc", "inc."):
                # Because some say "inc." and others say "inc"
                loader.add_language_node_and_attach(
                    language="inc",
                    node_type=obj_type,
                    pherc_display_name=ph_name,
                    cornice_display_name=cornice_name,
                    pezzo_display_name=pezzo_name,
                    disegni_name=disegni_name
                )
            else:
                loader.add_language_node_and_attach(
                    language=row['Language'],
                    node_type=obj_type,
                    pherc_display_name=ph_name,
                    language_url=row['LanguageURI'],
                    cornice_display_name=cornice_name,
                    pezzo_display_name=pezzo_name,
                    disegni_name=disegni_name                 
            )                      

        if row['UnrollerPerson']:
            # Since there can be multiple listed, split the string
            for unroller in row['UnrollerPerson'].split(','):
                loader.add_unroller_node_and_attach(
                    node_type=obj_type,
                    unroller_name=unroller.strip(),
                    pherc_display_name=ph_name,
                    cornice_display_name=cornice_name,
                    pezzo_display_name=pezzo_name,
                    disegni_name=disegni_name
                )

        if row['UnrollingMethod']:
            loader.add_unrolling_method_node_and_attach(
                node_type=obj_type,
                pherc_display_name=ph_name,
                unrolling_method_name=row['UnrollingMethod'],
                cornice_display_name=cornice_name,
                pezzo_display_name=pezzo_name,
                disegni_name=disegni_name
            )
        
        if row['OsloMethod'].casefold() == "Yes".casefold():
            loader.add_oslo_method_node_and_attach(
                node_type=obj_type,
                pherc_display_name=ph_name,
                cornice_display_name=cornice_name,
                pezzo_display_name=pezzo_name,
                disegni_name=disegni_name
            )
        
        if (row['Scorze'].casefold() == "Yes".casefold()) and (row['Scorze1'] is None):
            # If Scorze is "Yes" but Scorze1 is not set, set the Scorze property
            # This should be cleaned up on the CSV side
            loader.set_node_property(
                node_type=obj_type,
                property_name="scorze",
                value=row['Scorze'].casefold(),
                pherc_display_name=ph_name,
                cornice_display_name=cornice_name,
                pezzo_display_name=pezzo_name,
                disegni_name=disegni_name   
            )
        
        if row['PezziCount'].isnumeric():
            loader.set_node_property(
                node_type=obj_type,
                property_name="pezzi_count",
                value=row['PezziCount'],
                pherc_display_name=ph_name,
                cornice_display_name=cornice_name,
                pezzo_display_name=pezzo_name,
                disegni_name=disegni_name
            )

        if row['Author']:
            loader.add_author_node_and_attach(
                node_type=obj_type,
                pherc_display_name=ph_name,
                author_name=row['Author'],
                cornice_display_name=cornice_name,
                pezzo_display_name=pezzo_name,
                disegni_name=disegni_name
            )

        if row['CavalloScribalStyle']:
            for style in row['CavalloScribalStyle'].split(','):
                loader.add_cavallo_scribal_style_node_and_attach(
                    node_type=obj_type,
                    cavallo_scribal_style=style.strip(),
                    pherc_display_name=ph_name,
                    cornice_display_name=cornice_name,
                    pezzo_display_name=pezzo_name,
                    disegni_name=disegni_name
                )   
        
# Then read uuid csv file
with open(uuid_csv, 'r') as csvfile:
    reader = csv.DictReader(csvfile)

    for row in reader:
        educelab_id = row['EduceLab ID']
        uuid = row['UUID']
        ph_name = row["PHerc"]
        cor_pezzo_name = row['Pezzo/Cr']
        replacement_uuid = row['Replacement UUID']
    
        loader.add_EduceLabID(educelab_id, uuid)
    
        # Since this is not affected by other things, take care of this first
        if replacement_uuid:
            if _is_real_uuid(replacement_uuid):
                print(f"Adding replacement UUID {replacement_uuid} for {uuid}")
                loader.add_replacement_EduceLabID(uuid, replacement_uuid)
                # Make the replacement UUID the current uuid
                uuid = replacement_uuid
            else:
                # Sentinel like "discarded" or "." — original UUID is retired
                # without a successor. Flag the original; don't create a bogus
                # EduceLabID node from the sentinel string.
                print(f"Retiring UUID {uuid} (reason: {replacement_uuid!r})")
                loader.mark_educelabid_retired(uuid, reason=replacement_uuid)
    
        # Deal with edge cases!
        if uuid == "02160e53-71b8-52ba-bcd3-faf6c6917c66":
            loader.set_pherc_and_cornice_names(uuid, "221", "221", "1 (Fackelmann)")
            loader.set_pherc_and_pezzo_names(uuid, "465", "465", "465-II")
            loader.set_pherc_and_cornice_names(uuid, "466", "466", "1 (Fackelmann)")
            loader.set_pherc_and_pezzo_names(uuid, "467", "467", "467-1")
            loader.set_pherc_and_cornice_names(uuid, "1081", "1081", "1 (Fackelmann)")
        
        elif uuid == "d5b9ebc4-31a9-5368-90ac-eeb2893998db":
            for pherc_name in ["228", "444", "1063"]:
                loader.set_pherc_and_cornice_names(uuid, pherc_name, pherc_name, cor_pezzo_name)
        
        elif uuid == "6c88ad2a-7a6a-5055-b832-babd9f859f37":
            for pherc_name in ["244", "456", "461", "1603"]:
                loader.set_pherc_and_cornice_names(uuid, pherc_name, pherc_name, cor_pezzo_name)
    
        elif uuid == "4ca2ccaa-181d-5046-bb65-b18280595e79":
            loader.set_pherc_and_pezzo_names(uuid, "465", "465", "Scorza")
        
        elif uuid == "67105cd9-9755-5bd0-9194-2444874fd54a":
            loader.set_pherc_and_pezzo_names(uuid, "467", "467", "Scorza")
        
        elif uuid == "e94d8207-3802-57e9-a5bd-b8030a1935b9":
            loader.set_pherc_and_pezzo_names(uuid, "467", "467", "Scorza")
    
        else:
            # ALl other cases
            object_info = loader.look_up_object_by_uuid(uuid)

            if cor_pezzo_name:
                # cornice/pezzo column has a value
                if 'Pezzo' in object_info or 'Cornice' in object_info:
                    # EduceLabID is already linked to a Cornice/Pezzo from the
                    # metadata phase. The UUID sheet's short name (e.g. "1 (Oslo)")
                    # often differs from the metadata displayName (e.g. "1 (Osloense)"),
                    # so set it as a `name` alias on the existing node rather than
                    # MERGE-creating a duplicate keyed on a different displayName.
                    loader.set_alias_on_assigned_node(uuid, ph_name, cor_pezzo_name)
                elif 'PHerc' in object_info or 'Casetta' in object_info:
                    # UUID sits on the PHerc/Casetta itself; create the Cornice
                    # using the UUID sheet's name as displayName.
                    anchor = object_info.get('PHerc') or object_info.get('Casetta')
                    loader.set_pherc_and_cornice_names(uuid, anchor, ph_name, cor_pezzo_name)
                else:
                    # No node assigned to this UUID yet — fall back to creating
                    # PHerc/Cornice from the UUID sheet alone.
                    loader.add_pherc_and_cornice_nodes_from_uuid_sheet(uuid, ph_name, cor_pezzo_name)

            elif ph_name:
                # Use MERGE
                loader.set_ph_name(uuid, ph_name)
            else:
                pass

loader.close()          