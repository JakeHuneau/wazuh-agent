# Copyright (C) 2015-2023, Wazuh Inc.
# Created by Wazuh, Inc. <info@wazuh.com>.
# This program is free software; you can redistribute it and/or modify it under the terms of GPLv2

"""
This module contains all necessary components (fixtures, classes, methods) to configure the test for its execution.
"""

import os
import sys
import pytest
import boto3
from botocore.exceptions import ClientError
from typing import List

# qa-integration-framework imports
from wazuh_testing import session_parameters
from wazuh_testing.constants import platforms
from wazuh_testing.constants.paths import ROOT_PREFIX
from wazuh_testing.constants.paths.logs import WAZUH_LOG_PATH
from wazuh_testing.logger import logger
from wazuh_testing.modules.aws.utils import (
    create_bucket,
    upload_log_events,
    create_log_group,
    create_log_stream,
    create_flow_log,
    delete_vpc,
    delete_bucket,
    delete_log_group,
    delete_log_stream,
    delete_s3_db,
    delete_services_db,
    upload_bucket_file,
    generate_file,
    create_sqs_queue,
    get_sqs_queue_arn,
    set_sqs_policy,
    set_bucket_event_notification_configuration,
    delete_sqs_queue,
    delete_bucket_files
)
from wazuh_testing.tools.monitors.file_monitor import FileMonitor
from wazuh_testing.utils import configuration
from wazuh_testing.utils.file import truncate_file
from wazuh_testing.utils.services import control_service
from wazuh_testing.constants.aws import US_EAST_1_REGION


# - - - - - - - - - - - - - - - - - - - - - - - - -Pytest configuration - - - - - - - - - - - - - - - - - - - - - - -


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add command-line options to the tests.

    Args:
        parser (pytest.Parser): Parser for command line arguments and ini-file values.
    """
    parser.addoption(
        "--tier",
        action="append",
        metavar="level",
        default=None,
        type=int,
        help="only run tests with a tier level equal to 'level'",
    )
    parser.addoption(
        "--tier-minimum",
        action="store",
        metavar="minimum_level",
        default=-1,
        type=int,
        help="only run tests with a tier level greater or equal than 'minimum_level'"
    )
    parser.addoption(
        "--tier-maximum",
        action="store",
        metavar="maximum_level",
        default=sys.maxsize,
        type=int,
        help="only run tests with a tier level less or equal than 'minimum_level'"
    )


def pytest_collection_modifyitems(config: pytest.Config, items: List[pytest.Item]) -> None:
    """Deselect tests that do not match with the specified environment or tier.

    Args:
        config (pytest.Config): Access to configuration values, pluginmanager and plugin hooks.
        items (list): List of items where each item is a basic test invocation.
    """
    selected_tests = []
    deselected_tests = []
    _platforms = set([platforms.LINUX,
                      platforms.WINDOWS,
                      platforms.MACOS])

    for item in items:
        supported_platforms = _platforms.intersection(
            mark.name for mark in item.iter_markers())
        plat = sys.platform

        selected = True
        if supported_platforms and plat not in supported_platforms:
            selected = False

        # Consider only first mark
        levels = [mark.kwargs['level']
                  for mark in item.iter_markers(name="tier")]
        if levels and len(levels) > 0:
            tiers = item.config.getoption("--tier")
            if tiers is not None and levels[0] not in tiers:
                selected = False
            elif item.config.getoption("--tier-minimum") > levels[0]:
                selected = False
            elif item.config.getoption("--tier-maximum") < levels[0]:
                selected = False
        if selected:
            selected_tests.append(item)
        else:
            deselected_tests.append(item)

    config.hook.pytest_deselected(items=deselected_tests)
    items[:] = selected_tests


# - - - - - - - - - - - - - - - - - - - - - - -End of Pytest configuration - - - - - - - - - - - - - - - - - - - - - - -


@pytest.fixture(scope='session')
def load_wazuh_basic_configuration():
    """Load a new basic configuration to the manager"""
    # Load ossec.conf with all disabled settings
    minimal_configuration = configuration.get_minimal_configuration()

    # Make a backup from current configuration
    backup_ossec_configuration = configuration.get_wazuh_conf()

    # Write new configuration
    configuration.write_wazuh_conf(minimal_configuration)

    yield

    # Restore the ossec.conf backup
    configuration.write_wazuh_conf(backup_ossec_configuration)


@pytest.fixture()
def set_wazuh_configuration(test_configuration: dict) -> None:
    """Set wazuh configuration

    Args:
        test_configuration (dict): Configuration template data to write in the ossec.conf
    """
    # Save current configuration
    backup_config = configuration.get_wazuh_conf()

    # Configuration for testing
    test_config = configuration.set_section_wazuh_conf(test_configuration.get('sections'))

    # Set new configuration
    configuration.write_wazuh_conf(test_config)

    # Set current configuration
    session_parameters.current_configuration = test_config

    yield

    # Restore previous configuration
    configuration.write_wazuh_conf(backup_config)


@pytest.fixture()
def configure_local_internal_options_function(request):
    """Fixture to configure the local internal options file.

    It uses the test variable local_internal_options. This should be
    a dictionary wich keys and values corresponds to the internal option configuration, For example:
    local_internal_options = {'monitord.rotate_log': '0', 'syscheck.debug': '0' }

    Args:
        request (fixture): Provide information on the executing test function.

    """
    try:
        local_internal_options = request.param
    except AttributeError:
        try:
            local_internal_options = getattr(request.module, 'local_internal_options')
        except AttributeError:
            logger.debug('local_internal_options is not set')
            raise AttributeError('Error when using the fixture "configure_local_internal_options_module", no '
                                 'parameter has been passed explicitly, nor is the variable local_internal_options '
                                 'found in the module.') from AttributeError

    backup_local_internal_options = configuration.get_local_internal_options_dict()

    logger.debug(f"Set local_internal_option to {str(local_internal_options)}")
    configuration.set_local_internal_options_dict(local_internal_options)

    yield

    logger.debug(f"Restore local_internal_option to {str(backup_local_internal_options)}")
    configuration.set_local_internal_options_dict(backup_local_internal_options)


@pytest.fixture()
def restart_wazuh_function(request):
    """Restart before starting a test, and stop it after finishing.

       Args:
            request (fixture): Provide information on the executing test function.
    """
    # If there is a list of required daemons defined in the test module, restart daemons, else restart all daemons.
    try:
        daemons = request.module.REQUIRED_DAEMONS
    except AttributeError:
        daemons = []

    if len(daemons) == 0:
        logger.debug(f"Restarting all daemon")
        control_service('restart')
    else:
        for daemon in daemons:
            logger.debug(f"Restarting {daemon}")
            # Restart daemon instead of starting due to legacy used fixture in the test suite.
            control_service('restart', daemon=daemon)

    yield

    # Stop all daemons by default (daemons = None)
    if len(daemons) == 0:
        logger.debug(f"Stopping all daemons")
        control_service('stop')
    else:
        # Stop a list daemons in order (as Wazuh does)
        daemons.reverse()
        for daemon in daemons:
            logger.debug(f"Stopping {daemon}")
            control_service('stop', daemon=daemon)


@pytest.fixture()
def file_monitoring(request):
    """Fixture to handle the monitoring of a specified file.

    It uses the variable `file_to_monitor` to determinate the file to monitor. Default `LOG_FILE_PATH`

    Args:
        request (fixture): Provide information on the executing test function.
    """
    if hasattr(request.module, 'file_to_monitor'):
        file_to_monitor = getattr(request.module, 'file_to_monitor')
    else:
        file_to_monitor = WAZUH_LOG_PATH

    logger.debug(f"Initializing file to monitor to {file_to_monitor}")

    file_monitor = FileMonitor(file_to_monitor)
    setattr(request.module, 'log_monitor', file_monitor)

    yield

    truncate_file(file_to_monitor)
    logger.debug(f"Trucanted {file_to_monitor}")


@pytest.fixture()
def truncate_monitored_files() -> None:
    """Truncate all the log files and json alerts files before and after the test execution"""
    log_files = [WAZUH_LOG_PATH]

    for log_file in log_files:
        if os.path.isfile(os.path.join(ROOT_PREFIX, log_file)):
            truncate_file(log_file)

    yield

    for log_file in log_files:
        if os.path.isfile(os.path.join(ROOT_PREFIX, log_file)):
            truncate_file(log_file)


@pytest.fixture
def mark_cases_as_skipped(metadata):
    if metadata['name'] in ['alb_remove_from_bucket', 'clb_remove_from_bucket', 'nlb_remove_from_bucket']:
        pytest.skip(reason='ALB, CLB and NLB integrations are removing older logs from other region')


@pytest.fixture
def restart_wazuh_function_without_exception(daemon=None):
    """Restart all Wazuh daemons."""
    try:
        control_service("start", daemon=daemon)
    except ValueError:
        pass

    yield

    control_service('stop', daemon=daemon)


"""Boto3 client fixtures"""
# Use the environment variable or default to 'dev'
aws_profile = os.environ.get("AWS_PROFILE", "default")


@pytest.fixture()
def boto_session():
    """Create a boto3 Session using the system defined AWS profile."""
    return boto3.Session(profile_name=f'{aws_profile}')


@pytest.fixture()
def s3_client(boto_session: boto3.Session):
    """Create an S3 client to manage bucket resources.

    Args:
        boto_session (boto3.Session): Session used to create the client.

    Returns:
        boto3.resources.base.ServiceResource: S3 client to manage bucket resources.
    """
    return boto_session.resource(service_name="s3", region_name=US_EAST_1_REGION)


@pytest.fixture()
def ec2_client(boto_session: boto3.Session):
    """Create an EC2 client to manage VPC resources.

    Args:
        boto_session (boto3.Session): Session used to create the client.

    Returns:
        Service client instance: EC2 client to manage VPC resources.
    """
    return boto_session.client(service_name="ec2", region_name=US_EAST_1_REGION)


@pytest.fixture()
def logs_clients(boto_session: boto3.Session, metadata: dict):
    """Create CloudWatch Logs clients per region to manage CloudWatch resources.

    Args:
        boto_session (boto3.Session): Session used to create the client.
        metadata (dict): Metadata from the module to obtain the defined regions.

    Returns:
        list(Service client instance): CloudWatch client list to manage the service's resources in multiple regions.
    """
    # A client for each region is required to generate logs accordingly
    return [boto_session.client(service_name="logs", region_name=region)
            for region in metadata.get('regions', US_EAST_1_REGION).split(',')]


@pytest.fixture()
def sqs_client(boto_session: boto3.Session):
    """Create an SQS client to manage queues.

    Args:
        boto_session (boto3.Session): Session used to create the client.

    Returns:
        Service client instance: SQS client to manage the queue resources.
    """
    return boto_session.client(service_name="sqs", region_name=US_EAST_1_REGION)


"""Session fixtures"""


@pytest.fixture()
def buckets_manager(s3_client):
    """Initializes a set to manage the creation and deletion of the buckets used throughout the test session.

    Args:
        s3_client (boto3.resources.base.ServiceResource): S3 client used to manage the bucket resources.

    Yields:
        buckets (set): Set of buckets.
        s3_client (boto3.resources.base.ServiceResource): S3 client used to manage the bucket resources.
    """
    # Create buckets set
    buckets: set = set()

    yield buckets, s3_client

    # Delete all buckets created during execution
    for bucket in buckets:
        try:
            # Delete the bucket
            delete_bucket(bucket_name=bucket, client=s3_client)
        except ClientError as error:
            logger.error({
                "message": "Client error deleting bucket, delete manually",
                "resource_name": bucket,
                "error": str(error)
            })

        except Exception as error:
            logger.error({
                "message": "Broad error deleting bucket, delete manually",
                "resource_name": bucket,
                "error": str(error)
            })


@pytest.fixture()
def log_groups_manager(logs_clients):
    """Initializes a set to manage the creation and deletion of the log groups used throughout the test session.

    Args:
        logs_clients (list(Service client instance)): CloudWatch Logs client list to manage the CloudWatch resources.

    Yields:
        log_groups (set): Set of log groups.
        logs_clients (list(Service client instance)): CloudWatch Logs client list to manage the CloudWatch resources.
    """
    # Create log groups set
    log_groups: set = set()

    yield log_groups, logs_clients

    # Delete all resources created during execution
    for log_group in log_groups:
        try:
            for logs_client in logs_clients:
                delete_log_group(log_group_name=log_group, client=logs_client)
        except ClientError as error:
            logger.error({
                "message": "Client error deleting log_group, delete manually",
                "resource_name": log_group,
                "error": str(error)
            })
            raise error

        except Exception as error:
            logger.error({
                "message": "Broad error deleting log_group, delete manually",
                "resource_name": log_group,
                "error": str(error)
            })
            raise error


@pytest.fixture()
def sqs_manager(sqs_client):
    """Initializes a set to manage the creation and deletion of the sqs queues used throughout the test session.

    Args:
        sqs_client (Service client instance): SQS client to manage the SQS resources.

    Yields:
        sqs_queues (set): Set of SQS queues.
        sqs_client (Service client instance): SQS client to manage the SQS resources.
    """
    # Create buckets set
    sqs_queues: set = set()

    yield sqs_queues, sqs_client

    # Delete all resources created during execution
    for sqs in sqs_queues:
        try:
            delete_sqs_queue(sqs_queue_url=sqs, client=sqs_client)
        except ClientError as error:
            logger.error({
                "message": "Client error deleting sqs queue, delete manually",
                "resource_name": sqs,
                "error": str(error)
            })

        except Exception as error:
            logger.error({
                "message": "Broad error deleting sqs queue, delete manually",
                "resource_name": sqs,
                "error": str(error)
            })


"""S3 fixtures"""


@pytest.fixture()
def create_test_bucket(buckets_manager,
                       metadata: dict):
    """Create a bucket.

    Args:
        buckets_manager (fixture): Set of buckets.
        metadata (dict): Bucket information.
    """
    bucket_name = metadata["bucket_name"]
    bucket_type = metadata["bucket_type"]

    buckets, s3_client = buckets_manager
    try:
        # Create bucket
        create_bucket(bucket_name=bucket_name, client=s3_client)
        logger.debug(f"Created new bucket: type {bucket_name}")

        # Append created bucket to resource set
        buckets.add(bucket_name)

    except ClientError as error:
        logger.error({
            "message": "Client error creating bucket",
            "bucket_name": bucket_name,
            "bucket_type": bucket_type,
            "error": str(error)
        })
        raise

    except Exception as error:
        logger.error({
            "message": "Broad error creating bucket",
            "bucket_name": bucket_name,
            "bucket_type": bucket_type,
            "error": str(error)
        })
        raise


@pytest.fixture
def manage_bucket_files(metadata: dict, s3_client, ec2_client):
    """Upload a file to S3 bucket and delete after the test ends.

    Args:
        metadata (dict): Metadata to get the parameters.
        s3_client (boto3.resources.base.ServiceResource): S3 client used to manage the bucket resources.
        ec2_client (Service client instance): EC2 client to manage VPC resources.
    """
    # Get bucket name
    bucket_name = metadata['bucket_name']

    # Get bucket type
    bucket_type = metadata['bucket_type']

    # Get only_logs_after, regions, prefix and suffix if set to generate file accordingly
    file_creation_date = metadata.get('only_logs_after')
    regions = metadata.get('regions', US_EAST_1_REGION).split(',')
    prefix = metadata.get('path', '')
    suffix = metadata.get('path_suffix', '')

    # Check if the VPC type is the one to be tested
    vpc_bucket = bucket_type == 'vpcflow'

    # Check if logs need to be created
    log_number = metadata.get("expected_results", 1) > 0

    # Generate files
    if log_number:
        files_to_upload = []
        metadata['uploaded_file'] = ''
        try:
            if vpc_bucket:
                # Create VPC resources
                flow_log_id, vpc_id = create_flow_log(vpc_name=metadata['vpc_name'],
                                                      bucket_name=bucket_name,
                                                      client=ec2_client)
                metadata['flow_log_id'] = flow_log_id
                for region in regions:
                    data, key = generate_file(bucket_type=bucket_type,
                                              bucket_name=bucket_name,
                                              date=file_creation_date,
                                              region=region,
                                              prefix=prefix,
                                              suffix=suffix,
                                              flow_log_id=flow_log_id)
                    files_to_upload.append((data, key))
            else:
                for region in regions:
                    data, key = generate_file(bucket_type=bucket_type,
                                              bucket_name=bucket_name,
                                              region=region,
                                              prefix=prefix,
                                              suffix=suffix,
                                              date=file_creation_date)
                    files_to_upload.append((data, key))

            for data, key in files_to_upload:
                # Upload file to bucket
                upload_bucket_file(bucket_name=bucket_name,
                                   data=data,
                                   key=key,
                                   client=s3_client)

                logger.debug('Uploaded file: %s to bucket "%s"', key, bucket_name)

                # Set filename for test execution
                metadata['uploaded_file'] += key

        except ClientError as error:
            logger.error({
                "message": "Client error uploading file to bucket",
                "bucket_name": bucket_name,
                "error": str(error)
            })
            raise error

        except Exception as error:
            logger.error({
                "message": "Broad error uploading file to bucket",
                "bucket_name": bucket_name,
                "error": str(error)
            })
            raise error

    yield

    try:
        if log_number:
            # Delete all bucket files
            delete_bucket_files(bucket_name=bucket_name, client=s3_client)

            if vpc_bucket:
                # Delete VPC resources (VPC and Flow Log)
                delete_vpc(vpc_id=vpc_id, flow_log_id=flow_log_id, client=ec2_client)

    except ClientError as error:
        logger.error({
            "message": "Client error deleting resources from bucket",
            "bucket_name": bucket_name,
            "error": str(error)
        })
        raise error

    except Exception as error:
        logger.error({
            "message": "Broad error deleting resources from bucket",
            "bucket_name": bucket_name,
            "error": str(error)
        })
        raise error


"""CloudWatch fixtures"""


@pytest.fixture()
def create_test_log_group(log_groups_manager,
                          metadata: dict) -> None:
    """Create a log group.

    Args:
        log_groups_manager (tuple): Log groups set and CloudWatch clients.
        metadata (dict): Log group information.
    """
    # Get log group names
    log_group_names = metadata["log_group_name"].split(',')

    # If the resource_type is defined, then the resource must be created
    resource_creation = 'resource_type' in metadata

    log_groups, logs_clients = log_groups_manager

    try:
        if resource_creation:
            # Create log group
            for log_group in log_group_names:
                for logs_client in logs_clients:
                    create_log_group(log_group_name=log_group, client=logs_client)
                    logger.debug(f"Created log group: {log_group}")

                # Append created log group to resource list
                log_groups.add(log_group)

    except ClientError as error:
        logger.error({
            "message": "Client error creating log group",
            "log_group": log_group,
            "error": str(error)
        })
        raise

    except Exception as error:
        logger.error({
            "message": "Broad error creating log group",
            "log_group": log_group,
            "error": str(error)
        })
        raise


@pytest.fixture()
def create_test_log_stream(metadata: dict, log_groups_manager) -> None:
    """Create a log stream.

    Args:
        metadata (dict): Log group information.
        log_groups_manager (tuple): Log groups set and CloudWatch clients.
    """
    # Get log group names
    log_group_names = metadata["log_group_name"].split(',')

    # Get log stream
    log_stream_name = metadata['log_stream_name']

    # If the resource_type is defined, then the resource must be created
    resource_creation = 'resource_type' in metadata

    _, logs_clients = log_groups_manager

    try:
        if resource_creation:
            # Create log stream for each log group defined
            for log_group in log_group_names:
                for logs_client in logs_clients:
                    create_log_stream(log_group=log_group,
                                      log_stream=log_stream_name,
                                      client=logs_client)
                    logger.debug(f'Created log stream {log_stream_name} within log group {log_group}')

    except ClientError as error:
        logger.error({
            "message": "Client error creating log stream",
            "log_group": log_group,
            "error": str(error)
        })
        raise

    except Exception as error:
        logger.error({
            "message": "Broad error creating log stream",
            "log_group": log_group,
            "error": str(error)
        })
        raise


@pytest.fixture
def manage_log_group_events(metadata: dict, logs_clients):
    """Upload events to a log stream inside a log group and delete the log stream after the test ends.

    Args:
        metadata (dict): Metadata to get the parameters.
        logs_clients (list(Service client instance)): CloudWatch Logs client list to manage the CloudWatch resources.
    """
    # Get log group names
    log_group_names = metadata["log_group_name"].split(',')

    # Get log stream name
    log_stream_name = metadata["log_stream_name"]

    # Get number of events
    event_number = metadata.get("expected_results", 1)

    # If the resource_type is defined, then the resource must be created
    resource_creation = 'resource_type' in metadata

    try:
        if resource_creation:
            log_creation_date = metadata.get('only_logs_after')
            for log_group in log_group_names:
                for logs_client in logs_clients:
                    # Create log events in log group
                    upload_log_events(
                        log_stream=log_stream_name,
                        log_group=log_group,
                        date=log_creation_date,
                        type_json='discard_field' in metadata,
                        events_number=event_number,
                        client=logs_client
                    )

    except ClientError as error:
        logger.error({
            "message": "Client error uploading events to log stream",
            "log_group": log_group,
            "log_stream_name": log_stream_name,
            "error": str(error)
        })
        raise error

    except Exception as error:
        logger.error({
            "message": "Broad error uploading events to log stream",
            "log_group": log_group,
            "log_stream_name": log_stream_name,
            "error": str(error)
        })
        raise error

    yield


"""SQS fixtures"""


@pytest.fixture
def set_test_sqs_queue(metadata: dict, sqs_manager, s3_client) -> None:
    """Create a test SQS queue.

    Args:
        metadata (dict): The metadata for the SQS queue.
        sqs_manager (fixture): The SQS set for the test.
        s3_client (boto3.resources.base.ServiceResource): S3 client used to manage bucket resources.
    """
    # Get bucket name
    bucket_name = metadata["bucket_name"]
    # Get SQS name
    sqs_name = metadata["sqs_name"]

    sqs_queues, sqs_client = sqs_manager

    try:
        # Create SQS and get URL
        sqs_queue_url = create_sqs_queue(sqs_name=sqs_name, client=sqs_client)
        # Add it to sqs set
        sqs_queues.add(sqs_queue_url)

        # Get SQS Queue ARN
        sqs_queue_arn = get_sqs_queue_arn(sqs_url=sqs_queue_url, client=sqs_client)

        # Set policy
        set_sqs_policy(bucket_name=bucket_name,
                       sqs_queue_url=sqs_queue_url,
                       sqs_queue_arn=sqs_queue_arn,
                       client=sqs_client)

        # Set bucket notification configuration
        set_bucket_event_notification_configuration(bucket_name=bucket_name,
                                                    sqs_queue_arn=sqs_queue_arn,
                                                    client=s3_client)

    except ClientError as error:
        # Check if the sqs exist
        if error.response['Error']['Code'] == 'ResourceNotFound':
            logger.error(f"SQS Queue {sqs_name} already exists")
            raise error
        else:
            raise error

    except Exception as error:
        raise error


"""DB fixtures"""


@pytest.fixture
def clean_s3_cloudtrail_db():
    """Delete the DB file before and after the test execution."""
    delete_s3_db()

    yield

    delete_s3_db()


@pytest.fixture
def clean_aws_services_db():
    """Delete the DB file before and after the test execution."""
    delete_services_db()

    yield

    delete_services_db()
