"""
Test script for pipeline processing node methods in PhercGraphDatabaseLoader.
This script tests adding processing nodes for PGS, Spectral, and Registration operations.

Prerequisites: The following nodes must already exist in the database:
- EduceLabID {uuid: 6e31467a-7557-504b-a2ee-bd25c9318f86}
- PHerc {displayName: 118a, name: 118a}
- SpectralRaw {path: Dailies/Spectral/MVDaily_20220908/Bod_PHerc0118Cn10,
               uuid: 66a6a1bf-fee6-45e4-9fee-cfbdddefad98}
- PGSRaw {path: Dailies/20220908/pgs/Bod_PHerc0118Cn10_021010e5,
          uuid: 021010e5-8c90-4148-86c4-86a0df89}

Run with: uv run tests/test_pipeline_loader.py
"""

import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dataloader.pherc_graphdb_loader import PhercGraphDatabaseLoader

# Initialize the database connection
# Update these values if needed
loader = PhercGraphDatabaseLoader(uri=None, user=None, password=None)


def test_pgs_processing():
    """
    Test adding a PGS processing node.
    """
    print("\n=== Testing PGS Processing Node ===")

    # Test parameters from the user
    artifact_uuid = "6e31467a-7557-504b-a2ee-bd25c9318f86"
    op_type = "PGS"
    input_ds_path = "Dailies/20220908/pgs/Bod_PHerc0118Cn10_021010e5"
    output_ds_path = "/Tests/ProcessedPGS/20251218"
    slurm_id = "40506"
    pipeline_id = "20251218-124"
    date_time = datetime.now().isoformat()

    try:
        result = loader.add_image_processing_node(
            artifact_uuid=artifact_uuid,
            op_type=op_type,
            input_ds_path=input_ds_path,
            output_ds_path=output_ds_path,
            date_time=date_time,
            slurm_id=slurm_id,
            pipeline_id=pipeline_id
        )
        print(f"✓ PGS Processing node created successfully")
        print(f"  - Input: {input_ds_path}")
        print(f"  - Output: {output_ds_path}")
        print(f"  - SLURM ID: {slurm_id}")
        print(f"  - Pipeline ID: {pipeline_id}")
        print(f"  - Date/Time: {date_time}")
        print(f"  - Status: submitted")
        return True
    except Exception as e:
        print(f"✗ Failed to create PGS processing node: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_spectral_processing():
    """
    Test adding a Spectral processing node.
    """
    print("\n=== Testing Spectral Processing Node ===")

    # Test parameters from the user
    artifact_uuid = "6e31467a-7557-504b-a2ee-bd25c9318f86"
    op_type = "SPEC"
    input_ds_path = "Dailies/Spectral/MVDaily_20220908/Bod_PHerc0118Cn10"
    output_ds_path = "/Tests/ProcessedSpectral/20251218"
    slurm_id = "40519"
    pipeline_id = "20251218-124"
    date_time = datetime.now().isoformat()

    try:
        result = loader.add_image_processing_node(
            artifact_uuid=artifact_uuid,
            op_type=op_type,
            input_ds_path=input_ds_path,
            output_ds_path=output_ds_path,
            date_time=date_time,
            slurm_id=slurm_id,
            pipeline_id=pipeline_id
        )
        print(f"✓ Spectral Processing node created successfully")
        print(f"  - Input: {input_ds_path}")
        print(f"  - Output: {output_ds_path}")
        print(f"  - SLURM ID: {slurm_id}")
        print(f"  - Pipeline ID: {pipeline_id}")
        print(f"  - Date/Time: {date_time}")
        print(f"  - Status: submitted")
        return True
    except Exception as e:
        print(f"✗ Failed to create Spectral processing node: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_registration_processing():
    """
    Test adding a Registration processing node.
    """
    print("\n=== Testing Registration Processing Node ===")

    # Test parameters from the user
    artifact_uuid = "6e31467a-7557-504b-a2ee-bd25c9318f86"
    input_pgs_path = "/Tests/ProcessedPGS/20251218"
    input_spectral_path = "/Tests/ProcessedSpectral/20251218"
    registered_img_path = "Tests/Registered/20251218"
    slurm_id = "40526"
    pipeline_id = "20251218-124"
    date_time = datetime.now().isoformat()

    try:
        result = loader.add_registration_processing_node(
            artifact_uuid=artifact_uuid,
            date_time=date_time,
            slurm_id=slurm_id,
            input_pgs_path=input_pgs_path,
            input_spectral_path=input_spectral_path,
            registered_img_path=registered_img_path,
            pipeline_id=pipeline_id
        )
        print(f"✓ Registration Processing node created successfully")
        print(f"  - Input PGS: {input_pgs_path}")
        print(f"  - Input Spectral: {input_spectral_path}")
        print(f"  - Output Registered: {registered_img_path}")
        print(f"  - SLURM ID: {slurm_id}")
        print(f"  - Pipeline ID: {pipeline_id}")
        print(f"  - Date/Time: {date_time}")
        print(f"  - Status: submitted")
        return True
    except Exception as e:
        print(f"✗ Failed to create Registration processing node: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_web_processing():
    """
    Test adding a Web processing node.
    """
    print("\n=== Testing Web Processing Node ===")

    # Test parameters from the user
    artifact_uuid = "6e31467a-7557-504b-a2ee-bd25c9318f86"
    op_type = "WEB"
    input_ds_path = "Tests/Registered/20251218"
    output_ds_path = "/Tests/Web/20251218"
    slurm_id = "40537"
    pipeline_id = "20251218-124"
    date_time = datetime.now().isoformat()

    try:
        result = loader.add_image_processing_node(
            artifact_uuid=artifact_uuid,
            op_type=op_type,
            input_ds_path=input_ds_path,
            output_ds_path=output_ds_path,
            date_time=date_time,
            slurm_id=slurm_id,
            pipeline_id=pipeline_id
        )
        print(f"✓ Web Processing node created successfully")
        print(f"  - Input: {input_ds_path}")
        print(f"  - Output: {output_ds_path}")
        print(f"  - SLURM ID: {slurm_id}")
        print(f"  - Pipeline ID: {pipeline_id}")
        print(f"  - Date/Time: {date_time}")
        print(f"  - Status: submitted")
        return True
    except Exception as e:
        print(f"✗ Failed to create Web processing node: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_update_process_status():
    """
    Test updating the status of process nodes.
    """
    print("\n=== Testing Process Status Update ===")

    pipeline_id = "20251218-124"

    try:
        # Update PGS process status to "completed"
        result = loader.update_process_status(
            pipeline_id=pipeline_id,
            stage="PGS",
            property_name="status",
            value="completed"
        )
        print(f"✓ PGS Process status updated to 'completed'")
        print(f"  - Pipeline ID: {pipeline_id}")
        print(f"  - Stage: PGS")

        # Update Spectral process status to "completed"
        result = loader.update_process_status(
            pipeline_id=pipeline_id,
            stage="SPEC",
            property_name="status",
            value="completed"
        )
        print(f"✓ Spectral Process status updated to 'completed'")
        print(f"  - Pipeline ID: {pipeline_id}")
        print(f"  - Stage: SPEC")

        # Update Registration process status to "completed"
        result = loader.update_process_status(
            pipeline_id=pipeline_id,
            stage="REG",
            property_name="status",
            value="completed"
        )
        print(f"✓ Registration Process status updated to 'completed'")
        print(f"  - Pipeline ID: {pipeline_id}")
        print(f"  - Stage: REG")

        # Update Web process status to "completed"
        result = loader.update_process_status(
            pipeline_id=pipeline_id,
            stage="WEB",
            property_name="status",
            value="completed"
        )
        print(f"✓ Web Process status updated to 'completed'")
        print(f"  - Pipeline ID: {pipeline_id}")
        print(f"  - Stage: WEB")
        return True
    except Exception as e:
        print(f"✗ Failed to update process status: {e}")
        import traceback
        traceback.print_exc()
        return False


def cleanup_test_data():
    """
    Clean up the test processing nodes created during the test.
    WARNING: This will delete the pipeline and process nodes created in this test!
    """
    print("\n=== Cleaning up test data ===")
    response = input("Do you want to delete the test pipeline and process nodes? (yes/no): ")

    if response.lower() == 'yes':
        # Delete Pipeline and its Process nodes
        loader._run_query("""
            MATCH (p:Pipeline {pipeline_id: $pipeline_id})
            OPTIONAL MATCH (p)-[:STAGE_OF]-(proc:Process)
            OPTIONAL MATCH (proc)-[:OUTPUT]->(output)
            DETACH DELETE p, proc, output
        """, pipeline_id="20251218-124")

        print("✓ Test pipeline and process nodes cleaned up")
        print("  (Original data nodes like EduceLabID, PHerc, PGSRaw, SpectralRaw remain intact)")
    else:
        print("Skipping cleanup - test data preserved for inspection")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("Pipeline Processing Node Loader Test")
    print("="*60)

    try:
        # Verify connection
        loader.verify_conn()

        # Run tests
        pgs_test_passed = test_pgs_processing()
        spectral_test_passed = test_spectral_processing()
        registration_test_passed = test_registration_processing()
        web_test_passed = test_web_processing()
        status_test_passed = test_update_process_status()

        # Summary
        print("\n" + "="*60)
        print("Test Summary:")
        print(f"  PGS Processing Node: {'✓ PASSED' if pgs_test_passed else '✗ FAILED'}")
        print(f"  Spectral Processing Node: {'✓ PASSED' if spectral_test_passed else '✗ FAILED'}")
        print(f"  Registration Processing Node: {'✓ PASSED' if registration_test_passed else '✗ FAILED'}")
        print(f"  Web Processing Node: {'✓ PASSED' if web_test_passed else '✗ FAILED'}")
        print(f"  Status Update: {'✓ PASSED' if status_test_passed else '✗ FAILED'}")
        print("="*60)

        # Cleanup option
        cleanup_test_data()

    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        loader.close()
        print("\nDatabase connection closed.")
