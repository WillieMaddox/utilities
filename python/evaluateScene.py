from spaceNetUtilities import evalTools as eT
from spaceNetUtilities import geoTools as gT
import numpy as np
import csv
import multiprocessing
import time
import argparse


def writeAOISummaryToCSV(resultsDict, csvwriter):
    csvwriter.writerow(['TruthFile', resultsDict['TruthFile']])
    csvwriter.writerow(['ProposalFile', resultsDict['ProposalFile']])
    csvwriter.writerow(['AOI_Name', resultsDict['AOI_Name']])
    csvwriter.writerow(['Summary Results'])
    csvwriter.writerow(['F1Score Total', resultsDict['F1ScoreTotal']])
    csvwriter.writerow(['Precision', resultsDict['PrecisionTotal']])
    csvwriter.writerow(['Recall', resultsDict['RecalTotal']])
    csvwriter.writerow(['True Positive Total', resultsDict['TruePositiveTotal']])
    csvwriter.writerow(['False Positive Total', resultsDict['FalsePositiveTotal']])
    csvwriter.writerow(['False Negative Total', resultsDict['FalseNegativeTotal']])
    csvwriter.writerow([''])

    # resultsDict = {'AOI_Name': aoiName
    #                    'TruthFile': truth_fp,
    #                'ProposalFile': test_fp,
    #                'F1ScoreTotal': F1ScoreTotal,
    #                'PrecisionTotal': precision,
    #                'RecalTotal': recall,
    #                'TruePositiveTotal': true_pos_total,
    #                'FalsePositiveTotal': false_pos_total,
    #                'FalseNegativeTotal': false_neg_total,
    #                'PerImageStatsResultList': result_list,
    #                'OutputSummaryFile': resultsOutputFile}


def writePerChipToCSV(resultsDictList, csvwriter):
    resultsDict = resultsDictList[0]
    csvwriter.writerow(['ImageId', 'F1Score', 'True Positive Count', 'False Positive Count', 'False Negative Count'])
    for result in resultsDict['PerImageStatsResultList']:
        tmpList = [result[1]]
        tmpList.extend(result[0])
        csvwriter.writerow(tmpList)


def writeResultsToScreen(resultsDict):
    print('AOI of Interest', resultsDict['AOI_Name'])
    print('True_Pos_Total', resultsDict['TruePositiveTotal'])
    print('False_Pos_Total', resultsDict['FalsePositiveTotal'])
    print('False_Neg_Total', resultsDict['FalseNegativeTotal'])
    print('F1ScoreTotal', resultsDict['F1ScoreTotal'])


# resultsDict = {'AOI_Name': aoiName
#                    'TruthFile': truth_fp,
#                'ProposalFile': test_fp,
#                'F1ScoreTotal': F1ScoreTotal,
#                'PrecisionTotal': precision,
#                'RecalTotal': recall,
#                'TruePositiveTotal': true_pos_total,
#                'FalsePositiveTotal': false_pos_total,
#                'FalseNegativeTotal': false_neg_total,
#                'PerImageStatsResultList': result_list,
#                'OutputSummaryFile': resultsOutputFile}


def evaluateSpaceNetSolution(summaryTruthFile, summaryProposalFile, resultsOutputFile='', processgeoJson=False,
                             useParallelProcessing=False, minPolygonSize=0,
                             iouThreshold=0.5):
    truth_fp = summaryTruthFile
    test_fp = summaryProposalFile
    # check for cores available
    if useParallelProcessing:

        max_cpu = multiprocessing.cpu_count()
        parallel = True
    else:
        max_cpu = 1
        parallel = False

    # initialize scene counts
    # true_pos_counts = []
    # false_pos_counts = []
    # false_neg_counts = []

    t0 = time.time()
    # Start Ingest Of Truth and Test Case
    if processgeoJson:
        sol_polys = gT.import_summary_geojson(truth_fp, removeNoBuildings=False)
        prop_polys = gT.import_summary_geojson(test_fp)
        polyFlag = 'poly'
    else:
        sol_polys = gT.read_wkt_csv(truth_fp, removeNoBuildings=False)
        prop_polys = gT.read_wkt_csv(test_fp, groundTruthFile=False)
        polyFlag = 'polyPix'

    t1 = time.time()
    total = t1 - t0
    print('time of ingest: ', total)

    # inspect polygons to ensure they are not too small
    sol_polys = [p for p in sol_polys if p["ImageId"] > 0 and p[polyFlag].GetArea() > minPolygonSize]
    prop_polys = [p for p in prop_polys if p["ImageId"] > 0]

    # Speed up search by preprocessing ImageId and polygonIds

    test_image_ids = [p['ImageId'] for p in prop_polys if p['ImageId'] > 0]
    test_image_ids2 = [p['ImageId'] for p in sol_polys if p['ImageId'] > 0]
    test_image_ids.extend(test_image_ids2)
    test_image_ids = set(test_image_ids)

    prop_polysIdList = np.asarray([p['ImageId'] for p in prop_polys if p["ImageId"] >= 0 and p['BuildingId'] != -1])
    prop_polysPoly = np.asarray([p[polyFlag] for p in prop_polys if p["ImageId"] >= 0 and p['BuildingId'] != -1])

    sol_polysIdsList = np.asarray([p['ImageId'] for p in sol_polys if p["ImageId"] >= 0 and p['BuildingId'] != -1])
    sol_polysPoly = np.asarray([p[polyFlag] for p in sol_polys if p["ImageId"] >= 0 and p['BuildingId'] != -1])
    # bad_count = 0
    # F1ScoreList = []
    cpu_count = min(multiprocessing.cpu_count(), max_cpu)
    print('{}'.format(max_cpu))
    p = multiprocessing.Pool(processes=cpu_count)
    # ResultList = []

    eval_function_input_list = eT.create_eval_function_input((test_image_ids,
                                                              (prop_polysIdList, prop_polysPoly),
                                                              (sol_polysIdsList, sol_polysPoly)))

    # Calculate Values
    t3 = time.time()
    print('time For DataCreation {}s'.format(t3 - t1))

    # result_list = p.map(eT.evalfunction, eval_function_input_list)
    if not parallel:
        result_list = []
        for eval_input in eval_function_input_list:
            result_list.append(eT.evalfunction(eval_input, threshold=iouThreshold))
    else:
        result_list = p.map(eT.evalfunction, eval_function_input_list)

    result_listNP = np.asarray([item[0] for item in result_list])
    result_listName = [item[1] for item in result_list]
    AOIIndexList = []
    AOIList = ['Total', 'AOI_1_Rio', 'AOI_2_Vegas', 'AOI_3_Paris', 'AOI_4_Shanghai', 'AOI_5_Khartoum']
    resultsDictList = []
    for AOI in AOIList:
        if AOI != 'Total':
            AOIIndex = [i for i, s in enumerate(result_listName) if AOI in s]
            AOIIndexList.append(AOIIndex)
            result_sum = np.sum(result_listNP[AOIIndex], axis=0)
        else:
            AOIIndex = [i for i, s in enumerate(result_listName) if '' in s]
            AOIIndexList.append(AOIIndex)
            result_sum = np.sum(result_listNP, axis=0)

        # result_sum = np.sum(result_listNP, axis=0)
        true_pos_total = result_sum[1]
        false_pos_total = result_sum[2]
        false_neg_total = result_sum[3]
        if (float(true_pos_total) + float(false_pos_total)) > 0:
            precision = float(true_pos_total) / (float(true_pos_total) + float(false_pos_total))
        else:
            precision = 0

        if (float(true_pos_total) + float(false_neg_total)) > 0:
            recall = float(true_pos_total) / (float(true_pos_total) + float(false_neg_total))
        else:
            recall = 0

        if (precision + recall) > 0:
            F1ScoreTotal = 2.0 * precision * recall / (precision + recall)
        else:
            F1ScoreTotal = 0

        resultsDict = {'AOI_Name': AOI,
                       'TruthFile': truth_fp,
                       'ProposalFile': test_fp,
                       'F1ScoreTotal': F1ScoreTotal,
                       'PrecisionTotal': precision,
                       'RecalTotal': recall,
                       'TruePositiveTotal': true_pos_total,
                       'FalsePositiveTotal': false_pos_total,
                       'FalseNegativeTotal': false_neg_total,
                       'PerImageStatsResultList': result_list,
                       'OutputSummaryFile': resultsOutputFile}

        resultsDictList.append(resultsDict)
        writeResultsToScreen(resultsDict)

    if resultsOutputFile != '':
        with open(resultsOutputFile, 'w') as csvFile:
            csvwriter = csv.writer(csvFile, delimiter=',')
            for resultsDict in resultsDictList:
                writeAOISummaryToCSV(resultsDict, csvwriter)

            writePerChipToCSV(resultsDictList, csvwriter)

    return resultsDictList


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Evaluate Score for SpaceNet')
    parser.add_argument("summaryTruthFile",
                        help="The Location of Summary Ground Truth csv File"
                             "Summary File should have a header = ImageId, BuildingId, polygonPixWKT, polygonGeoPix "
                             "Format is '{},{},{},{}.format(ImageId, BuildingId, polygonPixWKT, polygonGeoPix)',"
                             "unless --geoJson flag is set"
                             "See spaceNet competition details for more information about file format")
    parser.add_argument("summaryProposalFile",
                        help="The Location of summary Propsal csv File"
                             "Summary File should have a header = ImageId, BuildingId, polygonPixWKT, Confidence "
                             "followed by values"
                             "Format is '{},{},{},{}.format(ImageId, BuildingId, polygonPixWKT, Confidence)'"
                             "unless --geoJson flag is set")
    parser.add_argument("--polygonMinimumPixels",
                        help="The minimum number of pixels a polygon must have to be considered valid"
                             "The minimum for spacenet round 2 is 20 pixels",
                        type=int,
                        default=20)
    parser.add_argument("--iouThreshold",
                        help="The IOU threshold for a True Positive"
                             "Spacenet uses 0.5",
                        type=float,
                        default=0.5)
    parser.add_argument("--resultsOutputFile",
                        help="If you would like summary data outwritten to a file, specify the file",
                        default='')
    parser.add_argument("--geoJson",
                        help='Convert Image from Native format to 8bit',
                        action='store_true')
    parser.add_argument("--useParallelProcessing",
                        help='Convert Image from Native format to 8bit',
                        action='store_true')

    args = parser.parse_args()
    # load Truth and Test File Locations

    summaryDict = evaluateSpaceNetSolution(args.summaryTruthFile,
                                           args.summaryProposalFile,
                                           resultsOutputFile=args.resultsOutputFile,
                                           processgeoJson=args.geoJson,
                                           useParallelProcessing=args.useParallelProcessing,
                                           minPolygonSize=args.polygonMinimumPixels,
                                           iouThreshold=args.iouThreshold)
