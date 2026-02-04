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

Run with:
  uv run tests/integration/test_pipeline_loader.py              # Interactive mode (create + ask to cleanup)
  uv run tests/integration/test_pipeline_loader.py --create     # Create nodes only, no cleanup
  uv run tests/integration/test_pipeline_loader.py --cleanup    # Cleanup only, no creation
"""

import argparse
from datetime import datetime

from educelab.hercdb.loader import PhercGraphDatabaseLoader

# Initialize the database connection
# Update these values if needed
loader = PhercGraphDatabaseLoader(uri=None, user=None, password=None)


def test_pgs_processing(params):
    """
    Test adding a PGS processing node.

    Args:
        params: Dictionary containing test parameters
    """
    print("\n=== Testing PGS Processing Node ===")

    try:
        result = loader.add_image_processing_node(
            artifact_uuid=params['artifact_uuid'],
            op_type="PGS",
            input_ds_path=params['pgs_input_path'],
            output_ds_path=params['pgs_output_path'],
            date_time=params['date_time'],
            slurm_id=params['pgs_slurm_id'],
            pipeline_id=params['pipeline_id']
        )
        print(f"✓ PGS Processing node created successfully")
        print(f"  - Input: {params['pgs_input_path']}")
        print(f"  - Output: {params['pgs_output_path']}")
        print(f"  - SLURM ID: {params['pgs_slurm_id']}")
        print(f"  - Pipeline ID: {params['pipeline_id']}")
        print(f"  - Date/Time: {params['date_time']}")
        print(f"  - Status: submitted")
        return True
    except Exception as e:
        print(f"✗ Failed to create PGS processing node: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_spectral_processing(params):
    """
    Test adding a Spectral processing node.

    Args:
        params: Dictionary containing test parameters
    """
    print("\n=== Testing Spectral Processing Node ===")

    try:
        result = loader.add_image_processing_node(
            artifact_uuid=params['artifact_uuid'],
            op_type="SPEC",
            input_ds_path=params['spectral_input_path'],
            output_ds_path=params['spectral_output_path'],
            date_time=params['date_time'],
            slurm_id=params['spectral_slurm_id'],
            pipeline_id=params['pipeline_id']
        )
        print(f"✓ Spectral Processing node created successfully")
        print(f"  - Input: {params['spectral_input_path']}")
        print(f"  - Output: {params['spectral_output_path']}")
        print(f"  - SLURM ID: {params['spectral_slurm_id']}")
        print(f"  - Pipeline ID: {params['pipeline_id']}")
        print(f"  - Date/Time: {params['date_time']}")
        print(f"  - Status: submitted")
        return True
    except Exception as e:
        print(f"✗ Failed to create Spectral processing node: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_registration_processing(params):
    """
    Test adding a Registration processing node.

    Args:
        params: Dictionary containing test parameters
    """
    print("\n=== Testing Registration Processing Node ===")

    try:
        result = loader.add_registration_processing_node(
            artifact_uuid=params['artifact_uuid'],
            date_time=params['date_time'],
            slurm_id=params['reg_slurm_id'],
            input_pgs_path=params['pgs_output_path'],
            input_spectral_path=params['spectral_output_path'],
            registered_img_path=params['registered_output_path'],
            pipeline_id=params['pipeline_id']
        )
        print(f"✓ Registration Processing node created successfully")
        print(f"  - Input PGS: {params['pgs_output_path']}")
        print(f"  - Input Spectral: {params['spectral_output_path']}")
        print(f"  - Output Registered: {params['registered_output_path']}")
        print(f"  - SLURM ID: {params['reg_slurm_id']}")
        print(f"  - Pipeline ID: {params['pipeline_id']}")
        print(f"  - Date/Time: {params['date_time']}")
        print(f"  - Status: submitted")
        return True
    except Exception as e:
        print(f"✗ Failed to create Registration processing node: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_web_processing(params):
    """
    Test adding a Web processing node.

    Args:
        params: Dictionary containing test parameters
    """
    print("\n=== Testing Web Processing Node ===")

    try:
        result = loader.add_image_processing_node(
            artifact_uuid=params['artifact_uuid'],
            op_type="WEB",
            input_ds_path=params['registered_output_path'],
            output_ds_path=params['web_output_path'],
            date_time=params['date_time'],
            slurm_id=params['web_slurm_id'],
            pipeline_id=params['pipeline_id']
        )
        print(f"✓ Web Processing node created successfully")
        print(f"  - Input: {params['registered_output_path']}")
        print(f"  - Output: {params['web_output_path']}")
        print(f"  - SLURM ID: {params['web_slurm_id']}")
        print(f"  - Pipeline ID: {params['pipeline_id']}")
        print(f"  - Date/Time: {params['date_time']}")
        print(f"  - Status: submitted")
        return True
    except Exception as e:
        print(f"✗ Failed to create Web processing node: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_update_process_status(params, stage, property_name="status", value="completed"):
    """
    Test updating the status of a process node.

    Args:
        params: Dictionary containing test parameters
        stage: The stage to update (e.g., "PGS", "SPEC", "REG", "WEB")
        property_name: The property to update (default: "status")
        value: The new value for the property (default: "completed")
    """
    print(f"\n=== Testing {stage} Process Status Update ===")

    try:
        result = loader.update_process_status(
            pipeline_id=params['pipeline_id'],
            stage=stage,
            property_name=property_name,
            value=value
        )
        print(f"✓ {stage} Process {property_name} updated to '{value}'")
        print(f"  - Pipeline ID: {params['pipeline_id']}")
        print(f"  - Stage: {stage}")
        return True
    except Exception as e:
        print(f"✗ Failed to update {stage} process {property_name}: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_empty_pipeline(pipeline_id):
    """
    Create a Pipeline node with no Process nodes attached.
    Used to test the 'unknown(error)' status case.

    Args:
        pipeline_id: The pipeline ID to create
    """
    print(f"\n=== Creating Empty Pipeline Node ===")

    try:
        loader._run_query("""
            MERGE (p:Pipeline {pipeline_id: $pipeline_id})
        """, pipeline_id=pipeline_id)
        print(f"✓ Empty Pipeline node created successfully")
        print(f"  - Pipeline ID: {pipeline_id}")
        print(f"  - No Process nodes attached")
        return True
    except Exception as e:
        print(f"✗ Failed to create empty pipeline: {e}")
        import traceback
        traceback.print_exc()
        return False


def cleanup_test_data(pipeline_id, interactive=True):
    """
    Clean up the test processing nodes created during the test.
    WARNING: This will delete the pipeline and process nodes for the specified pipeline ID!

    Args:
        pipeline_id: The pipeline ID to clean up
        interactive: If True, prompts for confirmation. If False, deletes without prompting.
    """
    print(f"\n=== Cleaning up test data for pipeline {pipeline_id} ===")

    if interactive:
        response = input("Do you want to delete the test pipeline and process nodes? (yes/no): ")
        if response.lower() != 'yes':
            print("Skipping cleanup - test data preserved for inspection")
            return

    # Delete Pipeline and its Process nodes
    loader._run_query("""
        MATCH (p:Pipeline {pipeline_id: $pipeline_id})
        OPTIONAL MATCH (p)-[:STAGE_OF]-(proc:Process)
        OPTIONAL MATCH (proc)-[:OUTPUT]->(output)
        DETACH DELETE p, proc, output
    """, pipeline_id=pipeline_id)

    print(f"✓ Pipeline {pipeline_id} and its process nodes cleaned up")
    print("  (Original data nodes like EduceLabID, PHerc, PGSRaw, SpectralRaw remain intact)")


def run_create_tests(test1_params, test2_params, test3_params, test4_params, test5_params):
    """Run all the creation tests for all test parameter sets."""
    # Run tests with test1_params - Full pipeline success
    print("\n" + "="*60)
    print("TEST 1: Full Pipeline Success (expected status: completed)")
    print("="*60)
    # PGS processing and status update
    test_pgs_processing(test1_params)
    test_update_process_status(test1_params, "PGS")

    # Spectral processing and status update
    test_spectral_processing(test1_params)
    test_update_process_status(test1_params, "SPEC")

    # Registration processing and status update
    test_registration_processing(test1_params)
    test_update_process_status(test1_params, "REG")

    # Web processing and status update
    test_web_processing(test1_params)
    test_update_process_status(test1_params, "WEB")

    # Run tests with test2_params - Registration fails, no Web processing
    print("\n" + "="*60)
    print("TEST 2: PGS and Spectral succeed, Registration fails (expected status: partially_completed)")
    print("="*60)
    # PGS processing and status update
    test_pgs_processing(test2_params)
    test_update_process_status(test2_params, "PGS")

    # Spectral processing and status update
    test_spectral_processing(test2_params)
    test_update_process_status(test2_params, "SPEC")

    # Registration processing - submit but mark as failed
    test_registration_processing(test2_params)
    test_update_process_status(test2_params, "REG", "status", "failed")
    print("\n  Note: Registration failed - skipping Web processing")

    # Run tests with test3_params - All stages submitted, none completed
    print("\n" + "="*60)
    print("TEST 3: All stages submitted, none completed (expected status: submitted)")
    print("="*60)
    # PGS processing - do NOT update status (leave as "submitted")
    test_pgs_processing(test3_params)
    # Spectral processing - do NOT update status (leave as "submitted")
    test_spectral_processing(test3_params)
    print("\n  Note: Both stages left in 'submitted' status")

    # Run tests with test4_params - All stages failed
    print("\n" + "="*60)
    print("TEST 4: All stages failed (expected status: failed)")
    print("="*60)
    # PGS processing and mark as failed
    test_pgs_processing(test4_params)
    test_update_process_status(test4_params, "PGS", "status", "failed")
    # Spectral processing and mark as failed
    test_spectral_processing(test4_params)
    test_update_process_status(test4_params, "SPEC", "status", "failed")
    print("\n  Note: Both stages marked as 'failed'")

    # Run tests with test5_params - Pipeline with no Process nodes
    print("\n" + "="*60)
    print("TEST 5: Pipeline with no Process nodes (expected status: unknown(error))")
    print("="*60)
    create_empty_pipeline(test5_params['pipeline_id'])
    print("\n  Note: Pipeline has no Process nodes attached")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Test pipeline processing node loader",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s              # Interactive mode: create nodes, then ask to cleanup
  %(prog)s --create     # Create nodes only, no cleanup
  %(prog)s --cleanup    # Cleanup only, no node creation
        """
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        '--create', action='store_true',
        help='Create test nodes only (no cleanup)'
    )
    mode_group.add_argument(
        '--cleanup', action='store_true',
        help='Cleanup test nodes only (no creation)'
    )
    args = parser.parse_args()

    print("\n" + "="*60)
    print("Pipeline Processing Node Loader Test")
    print("="*60)

    # Test parameters for test 1
    test1_params = {
        'artifact_uuid': '6e31467a-7557-504b-a2ee-bd25c9318f86',
        'pipeline_id': '20251218-124',
        'date_time': datetime.now().isoformat(),

        # PGS parameters
        'pgs_input_path': 'Dailies/20220908/pgs/Bod_PHerc0118Cn10_021010e5',
        'pgs_output_path': '/Tests/ProcessedPGS/20251218',
        'pgs_slurm_id': '40506',

        # Spectral parameters
        'spectral_input_path': 'Dailies/Spectral/MVDaily_20220908/Bod_PHerc0118Cn10',
        'spectral_output_path': '/Tests/ProcessedSpectral/20251218',
        'spectral_slurm_id': '40519',

        # Registration parameters
        'registered_output_path': 'Tests/Registered/20251218',
        'reg_slurm_id': '40526',

        # Web parameters
        'web_output_path': '/Tests/Web/20251218',
        'web_slurm_id': '40537'
    }

    # Test parameters for test 2
    # This test simulates PGS and Spectral succeeding, but Registration failing
    test2_params = {
        'artifact_uuid': 'dc67b901-4663-503b-8966-c8a111bcc5c5',
        'pipeline_id': '20251222-389',
        'date_time': datetime.now().isoformat(),

        # PGS parameters
        'pgs_input_path': 'Dailies/20221102/20221102_094008_PHerc1044Cr04_29388c5b',
        'pgs_output_path': '/Tests/ProcessedPGS/20251222',
        'pgs_slurm_id': '50273',

        # Spectral parameters
        'spectral_input_path': 'Dailies/Spectral/MVDaily_20221102/PHerc1044Cr04',
        'spectral_output_path': '/Tests/ProcessedSpectral/20251222',
        'spectral_slurm_id': '51222',

        # Registration parameters
        'registered_output_path': 'Tests/Registered/20251222',
        'reg_slurm_id': '51344'
    }

    # Test parameters for test 3
    # All stages submitted, none completed -> status = "submitted"
    test3_params = {
        'artifact_uuid': '6e31467a-7557-504b-a2ee-bd25c9318f86',  # Reuse from TEST 1
        'pipeline_id': '20260203-TEST3',
        'date_time': datetime.now().isoformat(),

        # PGS parameters
        'pgs_input_path': 'Dailies/20220908/pgs/Bod_PHerc0118Cn10_021010e5',
        'pgs_output_path': '/Tests/ProcessedPGS/20260203-TEST3',
        'pgs_slurm_id': '60001',

        # Spectral parameters
        'spectral_input_path': 'Dailies/Spectral/MVDaily_20220908/Bod_PHerc0118Cn10',
        'spectral_output_path': '/Tests/ProcessedSpectral/20260203-TEST3',
        'spectral_slurm_id': '60002',
    }

    # Test parameters for test 4
    # All stages failed -> status = "failed"
    test4_params = {
        'artifact_uuid': 'dc67b901-4663-503b-8966-c8a111bcc5c5',  # Reuse from TEST 2
        'pipeline_id': '20260203-TEST4',
        'date_time': datetime.now().isoformat(),

        # PGS parameters
        'pgs_input_path': 'Dailies/20221102/20221102_094008_PHerc1044Cr04_29388c5b',
        'pgs_output_path': '/Tests/ProcessedPGS/20260203-TEST4',
        'pgs_slurm_id': '60003',

        # Spectral parameters
        'spectral_input_path': 'Dailies/Spectral/MVDaily_20221102/PHerc1044Cr04',
        'spectral_output_path': '/Tests/ProcessedSpectral/20260203-TEST4',
        'spectral_slurm_id': '60004',
    }

    # Test parameters for test 5
    # Pipeline with no Process nodes -> status = "unknown(error)"
    test5_params = {
        'pipeline_id': '20260203-TEST5',
    }

    # Collect all pipeline IDs for cleanup
    all_pipeline_ids = [
        test1_params['pipeline_id'],
        test2_params['pipeline_id'],
        test3_params['pipeline_id'],
        test4_params['pipeline_id'],
        test5_params['pipeline_id'],
    ]

    try:
        # Verify connection
        loader.verify_conn()

        if args.cleanup:
            # Cleanup only mode
            print("\nRunning in CLEANUP ONLY mode")
            for pipeline_id in all_pipeline_ids:
                cleanup_test_data(pipeline_id, interactive=False)

        elif args.create:
            # Create only mode
            print("\nRunning in CREATE ONLY mode (no cleanup)")
            run_create_tests(test1_params, test2_params, test3_params, test4_params, test5_params)
            print("\n" + "="*60)
            print("Test nodes created and preserved for inspection.")
            print(f"Run with --cleanup to remove pipeline IDs:")
            for pipeline_id in all_pipeline_ids:
                print(f"  - {pipeline_id}")
            print("="*60)

        else:
            # Interactive mode (default): create then ask to cleanup
            print("\nRunning in INTERACTIVE mode (create + ask to cleanup)")
            run_create_tests(test1_params, test2_params, test3_params, test4_params, test5_params)
            for pipeline_id in all_pipeline_ids:
                cleanup_test_data(pipeline_id, interactive=True)

    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        loader.close()
        print("\nDatabase connection closed.")
