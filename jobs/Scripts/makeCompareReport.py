import sys
import json
import os
import argparse
from statistics import median

sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir)
        )
    )


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--work_dir', required=True)
    parser.add_argument('--execution_type', required=True)
    args = parser.parse_args()
    work_dir = args.work_dir

    json_files = list(
        filter(
            lambda x: x.endswith('RPR.json'), os.listdir(work_dir)
        )
    )

    reports = []

    for file in json_files:
        json_content = json.load(open(os.path.join(work_dir, file), 'r'))[0]

        if json_content.get('group_timeout_exceeded', False):
            json_content['message'].append('Test group timeout exceeded')

        log_key = '{}_log'.format(args.execution_type)

        min_latency = -1
        max_latency = -1
        latencies = []
        line_number = 0

        if log_key in json_content and os.path.exists(os.path.join(work_dir, json_content[log_key])):
            with open(os.path.join(work_dir, json_content[log_key]), 'r') as log_file:
                log = log_file.readlines()
                for line in log:
                    if 'latency' in line:
                        # Line example (sample format for client and server):
                        # 2021-05-31 09:01:55.469     3F90 [RemoteGamePipeline]    Info: Average latency: full 35.08, client  1.69, server 21.83, encoder  3.42, network 11.56, decoder  1.26, Rx rate: 122.67 fps, Tx rate: 62.33 fps
                        current_latency = float(line.split(':')[4].split(',')[0].replace('full', ''))

                        # skip first line with latency (it always contain latency value equals to 0.0)
                        if line_number != 0:
                            latencies.append(current_latency)

                            if min_latency == -1 or current_latency < min_latency:
                                min_latency = current_latency

                            if current_latency > max_latency:
                                max_latency = current_latency

                        line_number += 1

        if json_content["test_status"] != "skipped":
            median_latency_key = 'median_{}_latency'.format(args.execution_type)

            if len(latencies) > 0:
                json_content[median_latency_key] = median(latencies)

            if min_latency != -1:
                latency_key = 'min_{}_latency'.format(args.execution_type)
                json_content[latency_key] = min_latency

            if max_latency != -1:
                latency_key = 'max_{}_latency'.format(args.execution_type)
                json_content[latency_key] = max_latency
                
            if median_latency_key in json_content:
                if json_content[median_latency_key] >= 100 and json_content[median_latency_key] < 300:
                    json_content["test_status"] = "failed"
                elif json_content[median_latency_key] >= 300:
                    json_content["test_status"] = "failed"
                elif json_content[median_latency_key] == 0:
                    json_content["message"].append("Median {} latency is equal to 0".format(args.execution_type))
                    json_content["test_status"] = "error"
            else:
                json_content["message"].append("Could not find mentions of non-zero latency in {} log".format(args.execution_type))
                json_content["test_status"] = "error"

        reports.append(json_content)

    with open(os.path.join(work_dir, 'report_compare.json'), 'w') as f: json.dump(reports, f, indent=4)
