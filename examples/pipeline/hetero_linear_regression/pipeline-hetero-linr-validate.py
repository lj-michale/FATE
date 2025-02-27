#
#  Copyright 2019 The FATE Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

import argparse

from pipeline.backend.pipeline import PipeLine
from pipeline.component import DataTransform
from pipeline.component import HeteroLinR
from pipeline.component import Intersection
from pipeline.component import Reader
from pipeline.interface import Data
from pipeline.interface import Model

from pipeline.utils.tools import load_job_config


def main(config="../../config.yaml", namespace=""):
    # obtain config
    if isinstance(config, str):
        config = load_job_config(config)
    parties = config.parties
    guest = parties.guest[0]
    host = parties.host[0]
    arbiter = parties.arbiter[0]

    guest_train_data = [{"name": "motor_hetero_guest", "namespace": f"experiment{namespace}"},
                        {"name": "motor_hetero_guest", "namespace": f"experiment{namespace}"}]
    host_train_data = [{"name": "motor_hetero_host", "namespace": f"experiment{namespace}"},
                       {"name": "motor_hetero_host", "namespace": f"experiment{namespace}"}]

    pipeline = PipeLine().set_initiator(role='guest', party_id=guest).set_roles(guest=guest, host=host, arbiter=arbiter)

    reader_0 = Reader(name="reader_0")
    reader_0.get_party_instance(role='guest', party_id=guest).component_param(table=guest_train_data[0])
    reader_0.get_party_instance(role='host', party_id=host).component_param(table=host_train_data[0])

    reader_1 = Reader(name="reader_1")
    reader_1.get_party_instance(role='guest', party_id=guest).component_param(table=guest_train_data[1])
    reader_1.get_party_instance(role='host', party_id=host).component_param(table=host_train_data[1])

    data_transform_0 = DataTransform(name="data_transform_0")
    data_transform_1 = DataTransform(name="data_transform_1")

    data_transform_0.get_party_instance(
        role='guest',
        party_id=guest).component_param(
        with_label=True,
        label_name="motor_speed",
        label_type="float",
        output_format="dense")
    data_transform_0.get_party_instance(role='host', party_id=host).component_param(with_label=False)

    data_transform_1.get_party_instance(
        role='guest',
        party_id=guest).component_param(
        with_label=True,
        label_name="motor_speed",
        label_type="float",
        output_format="dense")
    data_transform_1.get_party_instance(role='host', party_id=host).component_param(with_label=False)

    intersection_0 = Intersection(
        name="intersection_0",
        intersect_method="rsa",
        rsa_params={"hash_method": "sha256", "final_hash_method": "sha256", "key_length": 1024})
    intersect_1 = Intersection(
        name="intersection_1",
        intersect_method="rsa",
        rsa_params={"hash_method": "sha256", "final_hash_method": "sha256", "key_length": 1024})

    hetero_linr_0 = HeteroLinR(name="hetero_linr_0", penalty="L2", optimizer="sgd", tol=0.001,
                               alpha=0.01, max_iter=20, early_stop="weight_diff", batch_size=-1,
                               learning_rate=0.15, decay=0.0, decay_sqrt=False,
                               init_param={"init_method": "zeros"},
                               encrypt_param={"key_length": 1024},
                               callback_param={"callbacks": ["EarlyStopping", "PerformanceEvaluate"],
                                               "validation_freqs": 1,
                                               "early_stopping_rounds": 5,
                                               "metrics": [
                                                   "mean_absolute_error",
                                                   "root_mean_squared_error"
                               ],
                                   "use_first_metric_only": False,
                                   "save_freq": 1
                               }
                               )

    pipeline.add_component(reader_0)
    pipeline.add_component(reader_1)
    pipeline.add_component(data_transform_0, data=Data(data=reader_0.output.data))
    pipeline.add_component(
        data_transform_1, data=Data(
            data=reader_1.output.data), model=Model(
            data_transform_0.output.model))

    pipeline.add_component(intersection_0, data=Data(data=data_transform_0.output.data))
    pipeline.add_component(intersect_1, data=Data(data=data_transform_1.output.data))

    pipeline.add_component(hetero_linr_0, data=Data(train_data=intersection_0.output.data,
                                                    validate_data=intersect_1.output.data))

    pipeline.compile()

    pipeline.fit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser("PIPELINE DEMO")
    parser.add_argument("-config", type=str,
                        help="config file")
    args = parser.parse_args()
    if args.config is not None:
        main(args.config)
    else:
        main()
