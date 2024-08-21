import logging
import helics as h
import numpy as np
from pydantic import BaseModel
import pandas as pd
from typing import List
import json
import csv
import pyarrow as pa
from datetime import datetime
from oedisi.types.data_types import MeasurementArray
from pathlib import Path

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)


class Recorder:
    def __init__(self, name, output_filepath, input_mapping):
        self.rng = np.random.default_rng(12345)
        deltat = 0.01
        # deltat = 60.

        # Create Federate Info object that describes the federate properties #
        fedinfo = h.helicsCreateFederateInfo()
        fedinfo.core_name = name
        fedinfo.core_type = h.HELICS_CORE_TYPE_ZMQ
        fedinfo.core_init = "--federates=1"
        logger.debug(name)

        h.helicsFederateInfoSetTimeProperty(
            fedinfo, h.helics_property_time_delta, deltat
        )

        self.vfed = h.helicsCreateValueFederate(name, fedinfo)
        logger.info("Value federate created")

        # Register the publication #
        self.sub = self.vfed.register_subscription(
            input_mapping["subscription"], "")
        self.output_filepath = output_filepath

    def run(self):
        # Enter execution mode #
        self.vfed.enter_initializing_mode()
        self.vfed.enter_executing_mode()
        logger.info("Entering execution mode")

        start = True
        granted_time = h.helicsFederateRequestTime(
            self.vfed, h.HELICS_TIME_MAXTIME)
        # for value_to_record in [1, 2]:
        #     feather_path = f"{self.output_filepath}/{name}_q.feather"
        #     csv_path = f"{self.output_filepath}/{name}_q.csv"
        #     if value_to_record == 1:
        #         feather_path = f"{self.output_filepath}/{name}_p.feather"
        #         csv_path = f"{self.output_filepath}/{name}_p.csv"
        p_data = []
        q_data = []
        columns = None
        while granted_time < h.HELICS_TIME_MAXTIME:
            logger.info("start time: " + str(datetime.now()))
            logger.debug(granted_time)
            # Check that the data is a MeasurementArray type
            sub_data = self.sub.json
            data_array = np.array(sub_data)
            equipment_ids = data_array[:, 0]
            p_data.append(list(data_array[:, 1]))
            q_data.append(list(data_array[:, 2]))
            if columns is None:
                columns = list(equipment_ids)
            # json_data = {}
            # json_data["time"] = granted_time
            # json_data["ids"] = list(equipment_ids.flatten())
            # json_data["values"] = list((value).flatten())
            # json_data["units"] = "kVA"
            # measurement = MeasurementArray(**json_data)

            # measurement_dict = {
            #     key: value
            #     for key, value in zip(measurement.ids, measurement.values)
            # }
            # measurement_dict["time"] = measurement.time.strftime(
            #     "%Y-%m-%d %H:%M:%S"
            # )
            # logger.debug(measurement.time)
            #
            # if start:
            #
            #     schema_elements = [(key, pa.float64())
            #                        for key in measurement.ids]
            #     schema_elements.append(("time", pa.string()))
            #     schema = pa.schema(schema_elements)
            #     writer = pa.ipc.new_file(sink, schema)
            #     start = False
            # cnt = 0
            #
            # writer.write_batch(
            #     pa.RecordBatch.from_pylist([measurement_dict]))
            #
            granted_time = h.helicsFederateRequestTime(
                self.vfed, h.HELICS_TIME_MAXTIME
            )
            logger.info("end time: " + str(datetime.now()))

        # data = pd.read_feather(feather_path)
        p_df = pd.DataFrame(p_data, columns=columns)
        q_df = pd.DataFrame(q_data, columns=columns)
        p_df.to_csv(f"{self.output_filepath}/{name}_p.csv", index=False)
        q_df.to_csv(f"{self.output_filepath}/{name}_q.csv", header=True, index=False)
        self.destroy()

    def destroy(self):
        h.helicsFederateDisconnect(self.vfed)
        logger.info("Federate disconnected")
        h.helicsFederateFree(self.vfed)
        h.helicsCloseLibrary()


if __name__ == "__main__":
    with open("static_inputs.json") as f:
        config = json.load(f)
        name = config["name"]
        _output_filepath = config["output_filepath"]
        _feather_path = config["feather_filename"]
        _csv_path = config["csv_filename"]

    with open("input_mapping.json") as f:
        input_mapping = json.load(f)

    sfed = Recorder(name, _output_filepath, input_mapping)
    sfed.run()
