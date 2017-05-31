"""
upload.py

Generate and upload UCSC Core Genomics data bundles from information passed via
excel or tsv file.

See "helper client" in:
https://ucsc-cgl.atlassian.net/wiki/display/DEV/Storage+Service+-+Functional+Spec
"""
import logging
from optparse import OptionParser
import sys
import csv
import os
import errno
import jsonschema
import openpyxl
import json
import uuid
import subprocess
import datetime
import copy
import semver
import requests
import dateutil
import hashlib
from functools import partial
from tqdm import tqdm
from fcntl import fcntl, F_GETFL, F_SETFL


def sha1sum(filename):
    logging.info("Calculating the sha1 sum for {}.".format(
        os.path.basename(filename)))
    filesize = os.path.getsize(filename)
    with open(filename, mode='rb') as f:
        d = hashlib.sha1()
        with tqdm(total=filesize, unit='B', unit_scale=True) as pbar:
            for buf in iter(partial(f.read, 128), b''):
                d.update(buf)
                pbar.update(len(buf))
        logging.info("sha1 sum done for {}".format(os.path.basename(filename)))
        return 'sha1$' + d.hexdigest()


def md5sum(filename):
    logging.info("Calculating the md5 checksum for {}.".format(
        os.path.basename(filename)))
    filesize = os.path.getsize(filename)
    with open(filename, mode='rb') as f:
        d = hashlib.md5()
        with tqdm(total=filesize, unit='B', unit_scale=True) as pbar:
            for buf in iter(partial(f.read, 128), b''):
                d.update(buf)
                pbar.update(len(buf))
        logging.info("md5 checksum done for {}".format(
            os.path.basename(filename)))
        return d.hexdigest()


def getValueFromObject(x, y):
    """
    Returns a value from a dictionary x if present. Otherwise returns an empty
    string
    """
    return x[y] if y in x else ''


def getOptions():
    """
    parse options
    """
    usage_text = []
    usage_text.append("%prog [options] [input Excel or tsv files]")

    description_text = []
    description_text.append("Upload client for Analysis Core")
    description_text.append("Performs the following operations:")
    description_text.append("1 Generates data bundles for the input files")
    description_text.append("2 Validates the metadata generates")
    description_text.append("3 Registers the data bundles with the server")
    description_text.append("4 Uploads the files")
    description_text.append("5 Returns receipt with UUIDs for all uploaded"
                            "files")

    usage_text.append("Data will be read from 'Sheet1' in the case of Excel "
                      "file.")

    parser = OptionParser(usage="\n".join(usage_text), description="\n"
                          .join(description_text))
    parser.add_option("-v", "--verbose", action="store_true", default=False,
                      dest="verbose", help="Switch for verbose mode.")
    parser.add_option("-s", "--skip-upload", action="store_true",
                      default=False, dest="skip_upload", help="Switch to skip "
                      "upload. Metadata files will be generated only.")
    parser.add_option("-t", "--test", action="store_true", default=False,
                      dest="test", help="Switch for development testing.")
    parser.add_option("-i", "--input-metadata-schema", action="store",
                      default="schemas/input_metadata.json", type="string",
                      dest="inputMetadataSchemaFileName",
                      help="flattened json schema file for input metadata")
    parser.add_option("-m", "--metadata-schema", action="store",
                      default="schemas/metadata_schema.json", type="string",
                      dest="metadataSchemaFileName",
                      help="flattened json schema file for metadata")
    parser.add_option("--registration-file", action="store",
                      default="registration.tsv", type="string",
                      dest="redwood_registration_file", help="file where "
                      "Redwood metadata upload registration manifest will be "
                      "written in. Existing file will be overwritten.")
    parser.add_option("-d", "--output-dir", action="store", default="/outputs",
                      type="string",
                      dest="metadataOutDir",
                      help="output directory. Existing files will be "
                      "overwritten.")
    parser.add_option("-r", "--receipt-file", action="store",
                      default="receipt.tsv", type="string", dest="receiptFile",
                      help="receipt file name. Includes UUID for all uploaded "
                      "files")
    parser.add_option("--submission-server-url", action="store",
                      default="http://storage2.ucsc-cgl.org:8460",
                      type="string", dest="submissionServerUrl",
                      help="URL for submission server.")
    parser.add_option("--force-upload", action="store_true", default=False,
                      dest="force_upload",
                      help="Force upload if object exists remotely. Overwrites"
                      " existing bundle.")
    parser.add_option("--skip-submit", action="store_true", default=False,
                      dest="skip_submit",
                      help="Skip contacting the submission server.")

    (options, args) = parser.parse_args()

    return (options, args, parser)


def jsonPP(obj):
    """
    Get a pretty stringified JSON
    """
    str = json.dumps(obj, indent=4, separators=(',', ': '), sort_keys=True)
    return str


def getNow():
    """
    Get a datetime object for utc NOW.
    Convert to ISO 8601 format with datetime.isoformat()
    """
    now = datetime.datetime.utcnow()
    return now


def getTimeDelta(startDatetime):
    """
    get a timedelta object. Get seconds elapsed with timedelta.total_seconds().
    """
    endDatetime = datetime.datetime.utcnow()
    timedeltaObj = endDatetime - startDatetime
    return timedeltaObj


def loadJsonObj(fileName):
    """
    Load a json object from a file.
    """
    try:
        file = open(fileName, "r")
        object = json.load(file)
        file.close()
    except:
        logging.error("Error loading and parsing {}".format(fileName))
    return object


def loadJsonSchema(fileName):
    """
    Load a json schema (actually just an object) from a file.
    """
    schema = loadJsonObj(fileName)
    return schema


def validateObjAgainstJsonSchema(obj, schema):
    """
    Validate an object against a schema.
    """
    try:
        jsonschema.validate(obj, schema)
    except Exception as exc:
        logging.error("Schemd json validation failed: %s" % (str(exc)))
        return False
    return True


def readFileLines(filename, strip=True):
    """
    Convenience method for getting an array of fileLines from a file.
    """
    with open(filename, 'r') as f:
        lines = [l.strip("\r\n") if strip else l for l in f.readlines()]
    return lines


def readTsv(fileLines, d="\t"):
    """
    convenience method for reading TSV file lines into csv.DictReader obj.
    """
    reader = csv.DictReader(fileLines, delimiter=d)
    return reader


def normalizePropertyName(inputStr):
    """
    field names in the schema are all lower-snake-case
    """
    newStr = inputStr.encode('ascii', 'ignore').lower()
    newStr = newStr.replace(" ", "_")
    newStr = newStr.strip()
    return newStr


def processFieldNames(dictReaderObj):
    """
    normalize the field names in a DictReader obj
    """
    newDataList = []
    for dict in dictReaderObj:
        newDict = {}
        newDataList.append(newDict)
        for key in dict.keys():
            newKey = normalizePropertyName(key)
            newDict[newKey] = dict[key]
    return newDataList


def generateUuid5(nameComponents, namespace=uuid.NAMESPACE_URL):
    """
    generate a uuid5 where the name is the lower case of concatenation
    of nameComponents
    """
    strings = []
    for nameComponent in nameComponents:
        # was having trouble with openpyxl data not being ascii
        strings.append(nameComponent.encode('ascii', 'ignore'))
    name = "".join(strings).lower()
    id = str(uuid.uuid5(namespace, name))
    return id


def setUuids(dataObj):
    """
    Set donor_uuid, specimen_uuid, and sample_uuid for dataObj.
    Uses uuid.uuid5().
    """
    keyFieldsMapping = {}
    keyFieldsMapping["donor_uuid"] = ["center_name", "submitter_donor_id"]

    keyFieldsMapping["specimen_uuid"] = list(keyFieldsMapping["donor_uuid"])
    keyFieldsMapping["specimen_uuid"].append("submitter_specimen_id")

    keyFieldsMapping["sample_uuid"] = list(keyFieldsMapping["specimen_uuid"])
    keyFieldsMapping["sample_uuid"].append("submitter_sample_id")

#     keyFieldsMapping["workflow_uuid"] = ["sample_uuid", "workflow_name",
# "workflow_version"]

    for uuidName in keyFieldsMapping.keys():
        keyList = []
        for field in keyFieldsMapping[uuidName]:
            if dataObj[field] is None:
                logging.error("%s not found in %s" % (field, jsonPP(dataObj)))
                return None
            else:
                keyList.append(dataObj[field])
        id = generateUuid5(keyList)
        dataObj[uuidName] = id

    # must follow sample_uuid assignment
    workflow_uuid_keys = ["sample_uuid", "workflow_name", "workflow_version"]
    keyList = []
    for field in workflow_uuid_keys:
        if dataObj[field] is None:
            logging.error("%s not found in %s" % (field, jsonPP(dataObj)))
            return None
        else:
            keyList.append(dataObj[field])
    id = generateUuid5(keyList)
    dataObj["workflow_uuid"] = id


def getDataObj(dict, schema):
    """
    Pull data out from dict. Use the flattened schema to get the key names
    as well as validate. If validation fails, return None.
    """
    setUuids(dict)

#     schema["properties"]["workflow_uuid"] = {"type": "string"}
    propNames = schema["properties"].keys()

    dataObj = {}
    for propName in propNames:
        dataObj[propName] = getValueFromObject(dict, propName)
        # dict[propName]

    if "workflow_uuid" in dict.keys():
        dataObj["workflow_uuid"] = dict["workflow_uuid"]

    isValid = validateObjAgainstJsonSchema(dataObj, schema)
    if (isValid):
        return dataObj
    else:
        logging.error("Validation failed for %s" % (jsonPP(dataObj)))
        return None


def getDataDictFromXls(fileName, sheetName="Sheet1"):
    """
    Get list of dict objects from .xlsx,.xlsm,.xltx,.xltm.
    """
    logging.debug("Attempt to read %s as xls file" % (fileName))
    workbook = openpyxl.load_workbook(fileName)
    sheetNames = workbook.get_sheet_names()
    logging.debug("Sheet names: %s" % (str(sheetNames)))

    worksheet = workbook.get_sheet_by_name(sheetName)

    headerRow = worksheet.rows[0]
    dataRows = worksheet.rows[1:]

    # map column index to column name
    colMapping = {}
    for colIdx in xrange(len(headerRow)):
        cell = headerRow[colIdx]
        value = cell.value
        if (value is not None):
            colMapping[colIdx] = normalizePropertyName(value)

    # build up list of row data objs
    data = []
    for row in dataRows:
        rowDict = {}
        data.append(rowDict)
        for colIdx in colMapping.keys():
            colName = colMapping[colIdx]
            value = row[colIdx].value
            rowDict[colName] = value

    return data


def ln_s(file_path, link_path):
    """
    ln -s
    note: will not clobber existing file
    """
    try:
        os.symlink(file_path, link_path)
    except OSError as exc:
        if exc.errno == errno.EEXIST:
            if os.path.isdir(link_path):
                logging.error("Linking failed -> %s is an existing directory"
                              % (link_path))
            elif os.path.isfile(link_path):
                logging.error("Linking failed -> %s is an existing file"
                              % (link_path))
            elif os.path.islink(link_path):
                logging.error("Linking failed -> %s is an existing link"
                              % (link_path))
        else:
            logging.error("Raising error")
            raise
    return None


def mkdir_p(path):
    """
    mkdir -p
    """
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise
    return None


def getWorkflowObjects(flatMetadataObjs):
    """
    For each flattened metadata object, build up a metadataObj with
    correct structure.
    """
    schema_version = "0.0.3"

    commonObjMap = {}
    for metaObj in flatMetadataObjs:
        workflow_uuid = metaObj["workflow_uuid"]
        if workflow_uuid in commonObjMap.keys():
            pass
        else:
            workflowObj = {}
            commonObjMap[workflow_uuid] = workflowObj
            workflowObj["program"] = metaObj["program"]
            workflowObj["project"] = metaObj["project"]
            workflowObj["center_name"] = metaObj["center_name"]
            workflowObj["submitter_donor_id"] = metaObj["submitter_donor_id"]
            workflowObj["donor_uuid"] = metaObj["donor_uuid"]
            # ADDING THE PRIMARY SITE; Since it is optional, if it isn't
            # present, it will be empty
            workflowObj["submitter_donor_primary_site"] = getValueFromObject(
                metaObj, "submitter_donor_primary_site"
            )
            # ^ metaObj["submitter_donor_primary_site"]
            workflowObj["timestamp"] = getNow().isoformat()
            workflowObj["schema_version"] = schema_version

            workflowObj["specimen"] = []

            # add specimen
            specObj = {}
            workflowObj["specimen"].append(specObj)
            specObj["submitter_specimen_id"] = metaObj["submitter_specimen_id"]
            specObj["submitter_specimen_type"] = metaObj[
                "submitter_specimen_type"
            ]
            specObj["submitter_experimental_design"] = metaObj[
                "submitter_experimental_design"
            ]
            specObj["specimen_uuid"] = metaObj["specimen_uuid"]
            specObj["samples"] = []

            # add sample
            sampleObj = {}
            specObj["samples"].append(sampleObj)
            sampleObj["submitter_sample_id"] = metaObj["submitter_sample_id"]
            sampleObj["sample_uuid"] = metaObj["sample_uuid"]
            sampleObj["analysis"] = []

            # add workflow
            workFlowObj = {}
            sampleObj["analysis"].append(workFlowObj)
            workFlowObj["workflow_name"] = metaObj["workflow_name"]
            workFlowObj["workflow_version"] = metaObj["workflow_version"]
            workFlowObj["analysis_type"] = metaObj["analysis_type"]
            workFlowObj["workflow_outputs"] = []
            workFlowObj["bundle_uuid"] = metaObj["workflow_uuid"]

        # retrieve workflow
        workflowObj = commonObjMap[workflow_uuid]
        # analysis_type = metaObj["analysis_type"]
        wf_outputsObj = workflowObj["specimen"][0]["samples"][0][
            "analysis"][0]["workflow_outputs"]

        # add file info
        fileInfoObj = {}
        wf_outputsObj.append(fileInfoObj)
        fileInfoObj["file_type"] = metaObj["file_type"]
        fileInfoObj["file_path"] = metaObj["file_path"]
        fileInfoObj["file_size"] = os.path.getsize(metaObj["file_path"])
        fileInfoObj["file_sha"] = sha1sum(metaObj["file_path"])

    return commonObjMap


def writeJson(directory, fileName, jsonObj):
    """
    Dump a json object to the specified directory/fileName. Creates directory
    if necessary.
    NOTE: will clobber the existing file
    """
    success = None
    try:
        mkdir_p(directory)
        filePath = os.path.join(directory, fileName)
        file = open(filePath, 'w')
        json.dump(jsonObj, file, indent=4, separators=(',', ': '),
                  sort_keys=True)
        success = 1
    except:
        logging.error("Error writing %s/%s" % (directory, fileName))
        success = 0
    finally:
        file.close()
    return success


def writeDataBundleDirs(structuredMetaDataObjMap, outputDir):
    """
    For each structuredMetaDataObj, prepare a data bundle dir for the workflow.
    Assumes one data bundle per structuredMetaDataObj. That means 1 specimen,
    1 sample, 1 analysis.
    """
    numFilesWritten = 0
    for workflow_uuid in structuredMetaDataObjMap.keys():
        metaObj = structuredMetaDataObjMap[workflow_uuid]

        # get outputDir (bundle_uuid)
        bundlePath = os.path.join(outputDir, workflow_uuid)

        # link data file(s)
        workflow_outputs = metaObj["specimen"][0]["samples"][0][
            "analysis"][0]["workflow_outputs"]
        for outputObj in workflow_outputs:
            file_path = outputObj["file_path"]
            # so I'm editing the file path here since directory
            # structures are stripped out upon upload
            file_name_array = file_path.split("/")
            outputObj["file_path"] = file_name_array[-1]
            fullFilePath = os.path.join(os.getcwd(), file_path)
            filename = os.path.basename(file_path)
            linkPath = os.path.join(bundlePath, filename)
            mkdir_p(bundlePath)
            ln_s(fullFilePath, linkPath)

        # write metadata
        numFilesWritten += writeJson(bundlePath, "metadata.json", metaObj)

    return numFilesWritten


def setupLogging(logfileName, logFormat, logLevel, logToConsole=True):
    """
    Setup simultaneous logging to file and console.
    """
    # logFormat = "%(asctime)s %(levelname)s %(funcName)s:%(lineno)d
    # %(message)s"
    logging.basicConfig(filename=logfileName, level=logging.NOTSET,
                        format=logFormat)
    if logToConsole:
        console = logging.StreamHandler()
        console.setLevel(logLevel)
        formatter = logging.Formatter(logFormat)
        console.setFormatter(formatter)
        logging.getLogger('').addHandler(console)
    return None


def add_to_registration(registration, bundle_id, project, file_path,
                        controlled_access):
    access = 'controlled' if controlled_access else 'open'
    registration.write('{}\t{}\t{}\t{}\t{}\n'.format(
        bundle_id, project, file_path, md5sum(file_path), access))


def register_upload(manifest, outdir):
    success = True
    command = "dcc-metadata-client -m {} -o {}".format(manifest, outdir)
    logging.info("registering upload redwood metadata: {}".format(command))
    try:
        subprocess.check_output(command, cwd=os.getcwd(),
                                stderr=subprocess.STDOUT, shell=True,
                                executable="/bin/bash")
    except subprocess.CalledProcessError as exc:
        success = False
        logging.error("error registering upload with redwood-metadata-server")
        writeJarExceptionsToLog(exc.output)
    return success


def perform_upload(manifest, force):
    success = True
    f = '--force' if force else ''
    command = "icgc-storage-client upload --manifest {} {}".format(manifest, f)
    logging.info("performing upload: {}".format(command))
#    try:
#        subprocess.check_output(command, cwd=os.getcwd(),
#                                stderr=subprocess.STDOUT, shell=True)
#    except subprocess.CalledProcessError as exc:
#        success = False
#        logging.error("error while uploading files")
#        writeJarExceptionsToLog(exc.output)
#    try:
    process = subprocess.Popen(command,
                               cwd=os.getcwd(),
                               stderr=subprocess.PIPE,
                               shell=True)
#    except Exception as exc:
#        success = False
#        logging.error("error while uploading files")
#        writeJarExceptionsToLog(str(exc))
#        return success
#    while True:
#        output = process.stderr.readline()
#        if output == '' and process.poll() is not None:
#            break
#        if output:
#            sys.stdout.write(output)
#            sys.stdout.flush()
#    return success
    flags = fcntl(process.stderr, F_GETFL)
    fcntl(process.stderr, F_SETFL, flags | os.O_NONBLOCK)
    while process.poll() is None:
        #output = process.stderr.read(process.stderr.fileno(), 1024)
#        output = os.read(process.stderr.fileno(), 1024)
#        if output:
#            sys.stdout.write(output)
#            sys.stdout.flush()
        try:
             sys.stdout.write(os.read(process.stderr.fileno(), 1024))
             sys.stdout.flush()
        except:
             continue
    success = False if process.returncode != 0 else True
    return success


def writeJarExceptionsToLog(errorOutput):
    """
    Output the 'ERROR' lines in the jar error output.
    """
    for line in errorOutput.split("\n"):
        line = line.strip()
        if (line.find("ERROR") != -1) and (line.find("main]") == -1):
            logging.error(line)
    return None


def parseUploadManifestFile(manifestFilePath):
    """
    from the upload manifest file, get the file_uuid for each uploaded file
    """
    idMapping = {}
    fileLines = readFileLines(manifestFilePath)
    for line in fileLines:
        fields = line.split()
        if fields[0] != "object-id":
            file_name = os.path.basename(fields[1])
            object_id = fields[0]
            idMapping[file_name] = object_id
    return idMapping


def collectReceiptData(manifestData, metadataObj):
    """
    collect the data for the upload receipt file The required fields are:
    program project center_name submitter_donor_id donor_uuid
    submitter_specimen_id specimen_uuid submitter_specimen_type
    submitter_sample_id sample_uuid analysis_type workflow_name
    workflow_version file_type file_path file_uuid bundle_uuid metadata_uuid
    """
    collectedData = []

    commonData = {}
    commonData["program"] = metadataObj["program"]
    commonData["project"] = metadataObj["project"]
    commonData["center_name"] = metadataObj["center_name"]
    commonData["submitter_donor_id"] = metadataObj["submitter_donor_id"]
    commonData["donor_uuid"] = metadataObj["donor_uuid"]
    # ADDING PRIMARY SITE
    commonData["submitter_donor_primary_site"] = getValueFromObject(
        metadataObj, "submitter_donor_primary_site")
    # ^ metadataObj["submitter_donor_primary_site"]

    commonData["submitter_specimen_id"] = \
        metadataObj["specimen"][0]["submitter_specimen_id"]
    commonData["specimen_uuid"] = metadataObj["specimen"][0]["specimen_uuid"]
    commonData["submitter_specimen_type"] = \
        metadataObj["specimen"][0]["submitter_specimen_type"]
    commonData["submitter_experimental_design"] = \
        metadataObj["specimen"][0]["submitter_experimental_design"]

    commonData["submitter_sample_id"] = \
        metadataObj["specimen"][0]["samples"][0]["submitter_sample_id"]
    commonData["sample_uuid"] = \
        metadataObj["specimen"][0]["samples"][0]["sample_uuid"]

    commonData["analysis_type"] = metadataObj["specimen"][0][
        "samples"][0]["analysis"][0]["analysis_type"]
    commonData["workflow_name"] = metadataObj["specimen"][0][
        "samples"][0]["analysis"][0]["workflow_name"]
    commonData["workflow_version"] = metadataObj["specimen"][0][
        "samples"][0]["analysis"][0]["workflow_version"]
    commonData["bundle_uuid"] = \
        metadataObj["specimen"][0]["samples"][0]["analysis"][0]["bundle_uuid"]
    commonData["metadata_uuid"] = manifestData["metadata.json"]

    workflow_outputs = metadataObj["specimen"][0][
        "samples"][0]["analysis"][0]["workflow_outputs"]
    for output in workflow_outputs:
        data = copy.deepcopy(commonData)
        data["file_type"] = output["file_type"]
        data["file_path"] = output["file_path"]

        fileName = os.path.basename(output["file_path"])
        data["file_uuid"] = manifestData[fileName]

        collectedData.append(data)

    return collectedData


def writeReceipt(collectedReceipts, receiptFileName, d="\t"):
    '''
    write an upload receipt file
    '''
    with open(receiptFileName, 'w') as receiptFile:
        fieldnames = [
            "program", "project", "center_name", "submitter_donor_id",
            "donor_uuid", "submitter_donor_primary_site",
            "submitter_specimen_id", "specimen_uuid",
            "submitter_specimen_type", "submitter_experimental_design",
            "submitter_sample_id", "sample_uuid", "analysis_type",
            "workflow_name", "workflow_version", "file_type", "file_path",
            "file_uuid", "bundle_uuid", "metadata_uuid"]
        writer = csv.DictWriter(receiptFile, fieldnames=fieldnames,
                                delimiter=d)

        writer.writeheader()
        writer.writerows(collectedReceipts)
    return None


def validateMetadataObjs(metadataObjs, jsonSchemaFile):
    '''
    validate metadata objects
    '''
    schema = loadJsonSchema(jsonSchemaFile)
    valid = []
    invalid = []
    for metadataObj in metadataObjs:
        isValid = validateObjAgainstJsonSchema(metadataObj, schema)
        if isValid:
            valid.append(metadataObj)
        else:
            invalid.append(metadataObj)

    obj = {"valid": valid, "invalid": invalid}
    return obj


def mergeDonors(metadataObjs):
    '''
    Merge data bundle metadata.json objects into correct donor objects.
    '''
    donorMapping = {}
    uuid_to_timestamp = {}

    for metaObj in metadataObjs:
        # check if donor exists
        donor_uuid = metaObj["donor_uuid"]

        if donor_uuid not in donorMapping:
            donorMapping[donor_uuid] = metaObj
            uuid_to_timestamp[donor_uuid] = [metaObj["timestamp"]]
            continue

        # check if specimen exists
        donorObj = donorMapping[donor_uuid]
        for specimen in metaObj["specimen"]:
            specimen_uuid = specimen["specimen_uuid"]

            savedSpecUuids = set()
            for savedSpecObj in donorObj["specimen"]:
                savedSpecUuid = savedSpecObj["specimen_uuid"]
                savedSpecUuids.add(savedSpecUuid)
                if specimen_uuid == savedSpecUuid:
                    specObj = savedSpecObj

            if specimen_uuid not in savedSpecUuids:
                donorObj["specimen"].append(specimen)
                continue

            # check if sample exists
            for sample in specimen["samples"]:
                sample_uuid = sample["sample_uuid"]

                savedSampleUuids = set()
                for savedSampleObj in specObj["samples"]:
                    savedSampleUuid = savedSampleObj["sample_uuid"]
                    savedSampleUuids.add(savedSampleUuid)
                    if sample_uuid == savedSampleUuid:
                        sampleObj = savedSampleObj

                if sample_uuid not in savedSampleUuids:
                    specObj["samples"].append(sample)
                    continue

                # check if analysis exists
                # need to compare analysis for uniqueness by looking at
                # analysis_type... bundle_uuid is not the right one here.
                for bundle in sample["analysis"]:
                    analysis_type = bundle["analysis_type"]
                    savedAnalysisTypes = set()
                    for savedBundle in sampleObj["analysis"]:
                        savedAnalysisType = savedBundle["analysis_type"]
                        savedAnalysisTypes.add(savedAnalysisType)
                        if analysis_type == savedAnalysisType:
                            analysisObj = savedBundle

                    if analysis_type not in savedAnalysisTypes:
                        sampleObj["analysis"].append(bundle)

                        # timestamp mapping
                        if "timestamp" in bundle:
                            uuid_to_timestamp[donor_uuid].append(
                                bundle["timestamp"])
                        continue
                    else:
                        # compare 2 analysis to keep only most relevant one
                        # saved is analysisObj
                        # currently being considered is bundle
                        new_workflow_version = bundle["workflow_version"]

                        saved_version = analysisObj["workflow_version"]
                        # current is older than new

                        if semver.compare(saved_version,
                                          new_workflow_version) == -1:
                            sampleObj["analysis"].remove(analysisObj)
                            sampleObj["analysis"].append(bundle)
                            # timestamp mapping
                            if "timestamp" in bundle:
                                uuid_to_timestamp[donor_uuid].append(
                                    bundle["timestamp"])

                        if semver.compare(saved_version,
                                          new_workflow_version) == 0:
                            # use the timestamp to choose analysis to
                            if "timestamp" in bundle and \
                               "timestamp" in analysisObj:
                                saved_timestamp = dateutil.parser.parse(
                                    analysisObj["timestamp"])
                                new_timestamp = dateutil.parser.parse(
                                    bundle["timestamp"])
                                timestamp_diff = \
                                    saved_timestamp - new_timestamp

                                if timestamp_diff.total_seconds() < 0:
                                    sampleObj["analysis"].remove(analysisObj)
                                    sampleObj["analysis"].append(bundle)
                                    # timestamp mapping
                                    if "timestamp" in bundle:
                                        uuid_to_timestamp[donor_uuid].append(
                                            bundle["timestamp"])

    # Get the  most recent timstamp from uuid_to_timestamp(for each donor) and
    # use donorMapping to substitute it
    for i in uuid_to_timestamp:
        timestamp_list = uuid_to_timestamp[i]
        donorMapping[i]["timestamp"] = max(timestamp_list)

    return donorMapping


def main():
    startTime = getNow()
    (options, args, parser) = getOptions()
    redwood_upload_manifest_dir = "redwoodUploadManifest"

    if len(args) == 0:
        logging.error("no input files")
        sys.exit(1)

    for dirName, subdirList, fileList in os.walk(options.metadataOutDir):
        if 'metadata.json' in fileList:
            logging.error("bundles from previous upload found in {}. Please"
                          " use a fresh directory".format(
                              options.metadataOutDir))
            sys.exit(1)

    if options.verbose:
        logLevel = logging.DEBUG
    else:
        logLevel = logging.INFO
    logfileName = os.path.basename(__file__).replace(".py", ".log")
    mkdir_p(options.metadataOutDir)
    logFilePath = os.path.join(options.metadataOutDir, logfileName)
    logFormat = "%(asctime)s %(levelname)s %(funcName)s:%(lineno)d %(message)s"
    setupLogging(logFilePath, logFormat, logLevel)

    # !!! careful not to expose the access token !!!
    printOptions = copy.deepcopy(vars(options))
    logging.debug('options:\t%s' % (str(printOptions)))
    logging.debug('args:\t%s' % (str(args)))

    # load flattened metadata schema for input validation
    inputMetadataSchema = loadJsonSchema(options.inputMetadataSchemaFileName)

    flatMetadataObjs = []

    # iter over input files
    for fileName in args:
        try:
            # attempt to process as xls file
            fileDataList = getDataDictFromXls(fileName)
        except:
            # attempt to process as tsv file
            # logging.info("couldn't read %s as excel file" % fileName)
            # logging.info("---now trying to read as tsv file")
            fileLines = readFileLines(fileName)
            reader = readTsv(fileLines)
            fileDataList = processFieldNames(reader)

        for data in fileDataList:
            metaObj = getDataObj(data, inputMetadataSchema)

            if metaObj is None:
                continue

            flatMetadataObjs.append(metaObj)

    # get structured workflow objects
    structuredWorkflowObjMap = getWorkflowObjects(flatMetadataObjs)

    if options.test:
        # donorObjMapping = mergeDonors(structuredWorkflowObjMap.values())
        validationResults = validateMetadataObjs(
            structuredWorkflowObjMap.values(), options.metadataSchemaFileName)
        numInvalidResults = len(validationResults["invalid"])
        if numInvalidResults != 0:
            logging.error("%s invalid merged objects found:"
                          % (numInvalidResults))
        else:
            logging.info("All merged objects validated")

    # validate metadata objects
    # exit script before upload
    validationResults = validateMetadataObjs(structuredWorkflowObjMap.values(),
                                             options.metadataSchemaFileName)
    numInvalidResults = len(validationResults["invalid"])
    if numInvalidResults != 0:
        logging.error("%s invalid metadata objects found:"
                      % (numInvalidResults))
        for metaObj in validationResults["invalid"]:
            logging.error("INVALID: %s" % (json.dumps(metaObj)))
        sys.exit(1)
    else:
        logging.info("validated all metadata objects for output")

    # write metadata files and link data files
    numFilesWritten = writeDataBundleDirs(
        structuredWorkflowObjMap, options.metadataOutDir)
    logging.info("number of metadata files written: %s"
                 % (str(numFilesWritten)))

    if (options.skip_upload):
        logging.info("Skipping data upload steps.")
        logging.info("A detailed log is at: %s" % (logFilePath))
        runTime = getTimeDelta(startTime).total_seconds()
        logging.info("Program ran for %s s." % str(runTime))
        return None
    else:
        logging.info("Uploading files.")
        logging.info("NOTE: If it hangs IP may be blocked")

    # UPLOAD SECTION
    counts = {}
    counts["bundlesFound"] = 0

    if not options.skip_submit:
        r = requests.post(
            options.submissionServerUrl + "/v0/submissions", json={})
        submission_id = json.loads(r.text)["submission"]["id"]
        logging.info("You can monitor the upload at {}/v0/submissions/{}"
                     .format(options.submissionServerUrl, submission_id))

    # build redwood registration manifest
    redwood_registration_manifest = os.path.join(
        options.metadataOutDir, options.redwood_registration_file)
    redwood_upload_manifest = None
    with open(redwood_registration_manifest, 'w') as registration:
        registration.write(
            'gnos_id\tprogram_code\tfile_path\tfile_md5\taccess\n')
        for dir_name, subdirs, files in os.walk(options.metadataOutDir):
            if dir_name == options.metadataOutDir:
                continue
            if len(subdirs) != 0:
                continue
            if "metadata.json" in files:
                bundleDirFullPath = os.path.join(os.getcwd(), dir_name)
                logging.debug("found bundle directory at %s"
                              % (bundleDirFullPath))
                counts["bundlesFound"] += 1

                bundle_metadata = loadJsonObj(
                    os.path.join(bundleDirFullPath, "metadata.json"))

                program = bundle_metadata["program"].strip().replace(' ', '_')
                bundle_uuid = os.path.basename(dir_name)
                controlled_access = True
                if redwood_upload_manifest is None:
                    redwood_upload_manifest = os.path.join(
                        options.metadataOutDir, redwood_upload_manifest_dir,
                        bundle_uuid)

                # register upload
                for f in files:
                    file = os.path.join(dir_name, f)
                    add_to_registration(registration, bundle_uuid, program,
                                        file, controlled_access)
            else:
                logging.info("no metadata file found in %s" % dir_name)

            logging.info("counts\t%s" % (json.dumps(counts)))

    # submit registration to metadata-server and perform upload
    mkdir_p(os.path.dirname(redwood_upload_manifest))
    reg_success = register_upload(redwood_registration_manifest,
                                  os.path.dirname(redwood_upload_manifest))
    if reg_success:
        if not perform_upload(redwood_upload_manifest, options.force_upload):
            logging.error("redwood upload failed")
            sys.exit(1)

    else:
        logging.error("upload registration failed")
        sys.exit(1)

    # generate receipt.tsv
    logging.info("now generate upload receipt")
    collected_receipts = []
    manifest_data = parseUploadManifestFile(redwood_upload_manifest)
    for dirName, subdirList, fileList in os.walk(options.metadataOutDir):
        if dirName == options.metadataOutDir \
                or os.path.basename(dirName) == redwood_upload_manifest_dir \
                or len(subdirList) != 0:
            continue
        if "metadata.json" in fileList:
            metadataFilePath = os.path.join(
                os.getcwd(), dirName, "metadata.json")
            metadataObj = loadJsonObj(metadataFilePath)

            receipt_data = collectReceiptData(manifest_data, metadataObj)
            for data in receipt_data:
                collected_receipts.append(data)
        else:
            logging.info("no manifest file found in %s" % dirName)

    receipt_file = os.path.join(options.metadataOutDir, options.receiptFile)
    writeReceipt(collected_receipts, receipt_file)

    # Sent the receipt to the submission server
    if not options.skip_submit:
        with open(receipt_file) as f:
            r = requests.put(options.submissionServerUrl
                             + "/v0/submissions/{}".format(submission_id),
                             json={"receipt": f.read()})
            logging.info("You can view the receipt at {}/v0/submissions/{}"
                         .format(options.submissionServerUrl, submission_id))

    logging.info("Upload succeeded. A detailed log is at: %s" % (logFilePath))
    runTime = getTimeDelta(startTime).total_seconds()
    logging.info("Upload took %s s." % str(runTime))
    logging.shutdown()
    return None


if __name__ == "__main__":
    main()
