"""
COPYRIGHT: Battelle Memorial, Pacific Northwest National Laboratory
This is following SGIDAL Working Example Template

This is a simple OPF federate that gets information from the grid Federate:
- It subscribes to:
    - Topology
    - Voltages
    - Powers
    - Tap Setpoints
    - Cap Bank Setpoints
- It publishes
    - load shedding setpoint
    - Tap regulator setpoints
    - Cap Bank Setpoints

@author: Sarmad Hanif
sarmad.hanif@pnnl.gov
"""
import helics as h
import logging
import numpy as np
from pydantic import BaseModel
from typing import List
import json
import sys
import opf_grid_utility_scripts
import timeit

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.DEBUG)

logger.debug(sys.executable)

class Complex(BaseModel):
    "Pydantic model for complex values with json representation"
    real: float
    imag: float


# class Topology(BaseModel):
#     "All necessary data for state estimator run"
#     y_matrix: List[List[Complex]]
#     phases: List[float]
#     base_voltages: List[float]
#     slack_bus: List[str]
#     unique_ids: List[str]

class Topology(BaseModel):
    "All necessary data for state estimator run"
    admittance: List[List[Complex]]
    base_voltage_angles: List[float]
    injections = List[float],
    base_voltage_magnitude: List[float]
    slack_bus: List[str]



class GenModelInfo(BaseModel):
    adj_matrix: List[List[float]]
    values: List[float]
    names: List[str]

class PVModelInfo(BaseModel):
    adj_matrix: List[List[float]]
    p_values: List[float]
    q_values: List[float]
    s_values: List[float]
    names: List[str]


class LabelledArray(BaseModel):
    values: List[float]
    ids: List[str]
    units: str

# class LabelledArray(BaseModel):
#     "Labelled array has associated list of ids"
#     array: List[float]
#     unique_ids: List[str]


class PolarLabelledArray(BaseModel):
    "Labelled arrays of magnitudes and angles with list of ids"
    magnitudes: List[float]
    angles: List[float]
    unique_ids: List[str]

def matrix_to_numpy(admittance: List[List[Complex]]):
    "Convert list of list of our Complex type into a numpy matrix"
    return np.array([[x[0] + 1j * x[1] for x in row] for row in admittance])

# def matrix_to_numpy(y_matrix: List[List[Complex]]):
#     "Convert list of list of our Complex type into a numpy matrix"
#     return np.array([[x.real + 1j * x.imag for x in row] for row in y_matrix])


def get_indices(topology, labelled_array):
    "Get list of indices in the topology for each index of the labelled array"
    inv_map = {v: i for i, v in enumerate(topology.unique_ids)}
    return [inv_map[v] for v in labelled_array.unique_ids]

def pol2cart(rho, phi):
    x = rho * np.cos(phi)
    y = rho * np.sin(phi)
    return x, y
class OptimalPowerFlowFederate:
    "Optimal Power Flow Federate. Wraps OPF with Pubs and Subs"

    def __init__(self, config, input_mapping):
        "Initializes federate with name and remaps input into subscriptions"

        deltat = 1.0
        fedinitstring = "--federates=1"

        logger.info("Creating Federate Info")
        fedinfo = h.helicsCreateFederateInfo()
        h.helicsFederateInfoSetCoreName(fedinfo, config['name'])
        h.helicsFederateInfoSetCoreTypeFromString(fedinfo, "zmq")
        h.helicsFederateInfoSetCoreInitString(fedinfo, fedinitstring)
        h.helicsFederateInfoSetTimeProperty(fedinfo, h.helics_property_time_delta, deltat)
        self.opf_fed = h.helicsCreateValueFederate(config['name'], fedinfo)

        # Create Federate Info object that describes the federate properties #
        self.config = config


        # fedinfo.core_name = config['name']
        # fedinfo.core_type = h.HELICS_CORE_TYPE_ZMQ
        # fedinfo.core_init = "--federates=1"
        # h.helicsFederateInfoSetTimeProperty(
        #     fedinfo, h.helics_property_time_delta, config['deltat']
        # )
        # self.config = config
        # self.opf_fed = h.helicsCreateValueFederate(config['name'], fedinfo)
        logger.info(f"OPF federate created - registering subscriptions")

        # Register the subsciption #
        self.sub_topology = self.opf_fed.register_subscription(
            input_mapping["topology"], ""
        )
        logger.info(f"topology subscribed")

        # self.sub_topology_flow = self.opf_fed.register_subscription(
        #     input_mapping["topology_flow"], ""
        # )
        # logger.info(f"topology_flow subscribed")

        self.sub_tap_info = self.opf_fed.register_subscription(
            input_mapping["tap_info"], ""
        )
        logger.info(f"tap_info subscribed")

        self.sub_cap_info = self.opf_fed.register_subscription(
            input_mapping["cap_info"], ""
        )
        logger.info(f"cap_info subscribed")

        self.sub_flex_info = self.opf_fed.register_subscription(
            input_mapping["flex_info"], ""
        )
        logger.info(f"flex_info subscribed")

        # self.sub_pv_info = self.opf_fed.register_subscription(
        #     input_mapping["pv_info"], ""
        # )
        # logger.info(f"pv_info subscribed")


        # self.sub_voltages_angle = self.opf_fed.register_subscription(
        #     input_mapping["voltage_angle"], "V"
        # )
        # logger.info(f"angle voltages subscribed")
        #
        # self.sub_voltages_mag = self.opf_fed.register_subscription(
        #     input_mapping["voltage_mag"], "V"
        # )
        # logger.info(f"magnitude voltages subscribed")

        self.sub_voltages_real = self.opf_fed.register_subscription(
            input_mapping["voltages_real"], "V"
        )
        logger.info(f"real voltages subscribed")

        self.sub_voltages_imag = self.opf_fed.register_subscription(
            input_mapping["voltages_imag"], "V"
        )
        logger.info(f"imaginary voltages subscribed")

        self.sub_powers_real = self.opf_fed.register_subscription(
            input_mapping["powers_real"], "W"
        )
        logger.info(f"active power load subscribed")

        self.sub_powers_imag = self.opf_fed.register_subscription(
            input_mapping["powers_imag"], "Var"
        )
        logger.info(f"reactive power load subscribed")

        self.sub_cap_powers_imag = self.opf_fed.register_subscription(
            input_mapping["cap_powers_imag"], "Var"
        )
        logger.info(f"cap_powers_imag subscribed")

        self.sub_pv_powers_real = self.opf_fed.register_subscription(
            input_mapping["pv_powers_real"], "W"
        )
        logger.info(f"pv_powers_real power subscribed")

        self.sub_pv_powers_imag = self.opf_fed.register_subscription(
            input_mapping["pv_powers_imag"], "Var"
        )
        logger.info(f"sub_pv_powers_imag power subscribed")

        self.sub_tap_values = self.opf_fed.register_subscription(
            input_mapping["tap_values"], ""
        )
        logger.info(f"sub_tap_values subscribed")

        # publishing to feeder
        self.opf_flex_powers_real = h.helicsFederateRegisterPublication(self.opf_fed, "opf_flex_powers_real",
                                                                            h.HELICS_DATA_TYPE_STRING, "")
        logger.info(f'real power to be published by OPF back to Feeder created')

        self.opf_cap_powers_imag = h.helicsFederateRegisterPublication(self.opf_fed, "opf_cap_powers_imag",
                                                                      h.HELICS_DATA_TYPE_STRING,
                                                                      "")
        logger.info(f'capacitor to be published by OPF back to Feeder created')

        self.opf_pv_powers_real = h.helicsFederateRegisterPublication(self.opf_fed, "opf_pv_powers_real",
                                                                     h.HELICS_DATA_TYPE_STRING, "")
        logger.info(f'real pv real power to be published by OPF back to Feeder created')

        self.opf_pv_powers_imag = h.helicsFederateRegisterPublication(self.opf_fed, "opf_pv_powers_imag",
                                                                     h.HELICS_DATA_TYPE_STRING, "")
        logger.info(f'imag pv power to be published by OPF back to Feeder created')

        self.opf_tap_values = h.helicsFederateRegisterPublication(self.opf_fed, "opf_tap_values",
                                                                 h.HELICS_DATA_TYPE_STRING, "")
        logger.info(f'tap values to be published by OPF back to Feeder created')


    def go_opf(self):
        logger.info(f'inside Run OPF Loop')

        "Enter execution and exchange data"
        # Enter execution mode #
        self.opf_fed.enter_executing_mode()
        logger.info("Entering execution mode")

        # seconds = 60*60*24
        # total_interval = int(seconds + 10)
        # logger.info(f'HELICS PROPERTY TIME PERIOD {h.HELICS_PROPERTY_TIME_PERIOD}')
        # update_interval = int(h.helicsFederateGetTimeProperty(self.opf_fed, h.HELICS_PROPERTY_TIME_PERIOD))
        # logger.info(f'update interval OPF Fed at start {update_interval}')

        # running a second later after DSS Federate
        # initial_time = self.config["start_time_index"]
        # logger.debug(f'Requesting initial time {initial_time}')
        # granted_time = h.helicsFederateRequestTime(self.opf_fed, initial_time)
        # logger.info(f'beginning granted time OPF Fed {granted_time}')
        granted_time = 0
        i = 0
        for request_time in range(0, int(self.config['number_of_timesteps'])):
            logger.info(f"requested time {request_time}")
            logger.info(f"number of time steps {config['number_of_timesteps']}")
            while granted_time < request_time:
                # logger.info(f'update interval OPF Fed {update_interval}')
                logger.info(f'previous granted time OPF Fed {granted_time}')
                # requested_time = (granted_time + update_interval)
                granted_time = h.helicsFederateRequestTime(self.opf_fed, request_time)
                logger.info(f'new granted time to OPF Fed by HELICS {granted_time}')

                # # logger.info(f'While loop with granted time: {granted_time} requested time: {requested_time}')
                # self.y_matrix = matrix_to_numpy(self.sub_topology.json['admittance']['admittance_matrix'])
                # logger.info(f'Subscribed Topology Received')

                # self.topology = Topology.parse_obj(self.sub_topology.json)
                # logger.info(f'Subscribed Topology Received')

                # # self.topology_flow = Topology.parse_obj(self.sub_topology_flow.json)
                # self.y_line = matrix_to_numpy(self.sub_topology_flow.json['admittance']['admittance_matrix'])
                # logger.info(f"Subscribed topology flow received")
                if i == 0:
                    # self.powers_P = LabelledArray.parse_obj(self.sub_powers_real.json)
                    self.powers_P = np.array(self.sub_powers_real.json['values'])
                    logger.info(f'Subscribed Active Power Received')

                    # self.powers_Q = LabelledArray.parse_obj(self.sub_powers_imag.json)
                    self.powers_Q = np.array(self.sub_powers_imag.json['values'])
                    logger.info(f'Subscribed Reactive Power Received')

                    # self.cap_Q = LabelledArray.parse_obj(self.sub_cap_powers_imag.json)
                    self.cap_Q = np.array(self.sub_cap_powers_imag.json['values'])
                    logger.info(f"cap_powers_imag received")
                    # logger.debug(f"{self.cap_Q.tolist()}")

                    # self.pv_P = LabelledArray.parse_obj(self.sub_pv_powers_real.json)
                    self.pv_P = np.array(self.sub_pv_powers_real.json['values'])

                    logger.info(f"sub_pv_powers_real power received")
                    # logger.debug(f"{self.pv_P.tolist()}")

                    # self.pv_Q = LabelledArray.parse_obj(self.sub_powers_imag.json)
                    self.pv_Q = np.array(self.sub_powers_imag.json['values'])
                    logger.info(f"sub_pv_powers_imag  imag received")
                    # logger.info(f"{self.pv_Q.tolist()}")

                    self.tap_vals = np.array(self.sub_tap_values.json['values'])
                    logger.info(f"sub_tap_values received")
                    # logger.info(f"tap vals received {self.tap_vals.tolist()}")

                    self.tap_info = GenModelInfo.parse_obj(self.sub_tap_info.json)
                    logger.info(f"tap_info received")

                    self.cap_info = GenModelInfo.parse_obj(self.sub_cap_info.json)
                    # logger.debug(f"self.cap_info {self.cap_info}")
                    logger.info(f"cap_info received")

                    self.flex_info = GenModelInfo.parse_obj(self.sub_flex_info.json)
                    logger.info(f"flex_info received")

                    # self.pv_info = PVModelInfo.parse_obj(self.sub_pv_info.json)
                    # logger.info(f"pv_info received")
                    # # TODO: check why the s values are not coming directly
                    # self.pv_s_init = np.array(
                    #     np.sqrt(np.array(self.pv_info.p_values) ** 2 + np.array(self.pv_info.q_values) ** 2))
                    # logger.info(f'real voltages subscribed {self.sub_voltages_real.json}')

                    # # dynamic states, which may change
                    # # TODO: check whether we can make this come from WLS and not from feeder (topology)
                    # self.voltages_mag = np.array(self.sub_topology.json['base_voltage_magnitudes']['values'])
                    # self.voltages_angle = np.array(self.sub_topology.json['base_voltage_angles']['values'])
                    # logger.info(f'Subscribed angle Voltages from topology from feeder')
                    #
                    # # self.voltages_angle = LabelledArray.parse_obj(self.sub_voltages_angle.json)
                    # # logger.info(f'Subscribed angle Voltages Received from WLS')
                    # # logger.info(f'self.voltages_angle = {self.voltages_angle}')
                    # # self.voltages_mag = LabelledArray.parse_obj(self.sub_voltages_mag.json)
                    # # logger.info(f'Subscribed mag Voltages Received from WLS')
                    # # logger.info(f'self.voltages_mag = {self.voltages_mag}')
                    #
                    # voltages_real_wls = self.voltages_angle
                    # voltages_imag_wls = self.voltages_mag
                    #
                    # # state estimator is calculating voltages in LL rather than LN
                    # voltages_real, voltages_imag = pol2cart(self.voltages_mag / np.sqrt(3), self.voltages_angle)
                    # voltages_real_wls = voltages_real.tolist()
                    # voltages_imag_wls = voltages_imag.tolist()
                    #
                    # logger.info(f'self.voltages_real from wls = {voltages_real_wls}')
                    # logger.info(f'self.voltages_imag from wls = {voltages_imag_wls}')
                    #
                    # self.voltages_real = voltages_real_wls
                    # self.voltages_imag = voltages_imag_wls

                    self.voltages_real = self.sub_voltages_real.json['values']
                    logger.info(f'Subscribed REAL Voltages Received')

                    self.voltages_imag = self.sub_voltages_imag.json['values']
                    logger.info(f'Subscribed Imag Voltages Received')
                    # logger.info(f'self.voltages_real from feeder = {self.voltages_real}')
                    # logger.info(f'self.voltages_imag from feeder = {self.voltages_imag}')

                    # self.y_matrix = matrix_to_numpy(self.sub_topology.json['admittance']['admittance_matrix'])

                    opf_grid_utility_scripts.unpack_fdrvals_mats(self)
                    opf_grid_utility_scripts.unpack_fdrvals_vecs(self)

                    logger.info(f"all grid quantities received")
                    logger.info(f"formulating the linear model")
                    t1 = timeit.default_timer()
                    opf_grid_utility_scripts.get_sens_matrices(self)
                    t2 = timeit.default_timer()
                    logger.info(f'sensitivity matrices obtained in {t2 - t1} seconds')
                    opf_grid_utility_scripts.solve_distributed_optimization(self)
                    logger.info("optimization complete passing the optimized variable setpoints to grid federate")

                    self.opf_flex_powers_real.publish(
                        LabelledArray(values=list(self.p_flex_load_var_opti), ids=self.flex_info.names, units='W').json())
                    logger.info(f'powers_real published to feeder')

                    self.opf_cap_powers_imag.publish(
                        LabelledArray(values=list(self.cap_value_opti), ids=self.cap_info.names, units='Var').json())
                    logger.info(f'cap_powers_imag published published to feeder')

                    self.opf_pv_powers_real.publish(
                        LabelledArray(values=list(np.squeeze(np.asarray(self.p_pv_opti))), ids=self.pv_names, units='W').json())
                    logger.info(f'pv_powers_real published to feeder')

                    self.opf_pv_powers_imag.publish(
                        LabelledArray(values=list(np.squeeze(np.asarray(self.q_pv_opti))), ids=self.pv_names, units='Var').json())
                    logger.info(f'pv_powers_imag published to feeder')
                i += 1
        self.destroy()

                # self.opf_pv_powers_real.publish(
                #     LabelledArray(values=list(self.p_pv_opti), ids=self.pv_info.names, units='W').json())
                # logger.info(f'pv_powers_real published to feeder')
                #
                #
                # self.opf_pv_powers_imag.publish(
                #     LabelledArray(values=list(self.q_pv_opti), ids=self.pv_info.names, units='Var').json())
                # logger.info(f'pv_powers_imag published to feeder')

                # logger.info(f"pv names {self.pv_names}")
                # logger.info(f"pv p vals {self.p_pv_opti}")
                # logger.info(f"pv q vals {self.q_pv_opti}")

                # if int(granted_time+3) % (5) == 0:
                #     # 5 seconds delay
                #     # initialization - this could be done before the loop starts too.
                #     # if granted_time <= 60*60: # first time ever, we'd need to load up all vectors and matrices
                #     # self.topology = Topology.parse_obj(self.sub_topology.json)
                #     self.y_matrix = matrix_to_numpy(self.sub_topology.json['admittance']['admittance_matrix'])
                #     logger.info(f'Subscribed Topology Received')
                #
                #     # self.topology = Topology.parse_obj(self.sub_topology.json)
                #     # logger.info(f'Subscribed Topology Received')
                #
                #     # # self.topology_flow = Topology.parse_obj(self.sub_topology_flow.json)
                #     # self.y_line = matrix_to_numpy(self.sub_topology_flow.json['admittance']['admittance_matrix'])
                #     # logger.info(f"Subscribed topology flow received")
                #
                #     self.tap_info = GenModelInfo.parse_obj(self.sub_tap_info.json)
                #     logger.info(f"tap_info received")
                #
                #     self.cap_info = GenModelInfo.parse_obj(self.sub_cap_info.json)
                #     logger.debug(f"self.cap_info {self.cap_info}")
                #     logger.info(f"cap_info received")
                #
                #     self.flex_info = GenModelInfo.parse_obj(self.sub_flex_info.json)
                #     logger.info(f"flex_info received")
                #
                #     # self.pv_info = PVModelInfo.parse_obj(self.sub_pv_info.json)
                #     # logger.info(f"pv_info received")
                #     # #TODO: check why the s values are not coming directly
                #     # self.pv_s_init = np.array(np.sqrt(np.array(self.pv_info.p_values)**2 + np.array(self.pv_info.q_values)**2))
                #     # # logger.info(f'real voltages subscribed {self.sub_voltages_real.json}')
                #
                #     # dynamic states, which may change
                #     # TODO: check whether we can make this come from WLS and not from feeder (topology)
                #     self.voltages_mag = np.array(self.sub_topology.json['base_voltage_magnitudes']['values'])
                #     self.voltages_angle = np.array(self.sub_topology.json['base_voltage_angles']['values'])
                #     logger.info(f'Subscribed angle Voltages from topology from feeder')
                #
                #     # self.voltages_angle = LabelledArray.parse_obj(self.sub_voltages_angle.json)
                #     # logger.info(f'Subscribed angle Voltages Received from WLS')
                #     # logger.info(f'self.voltages_angle = {self.voltages_angle}')
                #     # self.voltages_mag = LabelledArray.parse_obj(self.sub_voltages_mag.json)
                #     # logger.info(f'Subscribed mag Voltages Received from WLS')
                #     # logger.info(f'self.voltages_mag = {self.voltages_mag}')
                #
                #     voltages_real_wls = self.voltages_angle
                #     voltages_imag_wls = self.voltages_mag
                #
                #
                #     # state estimator is calculating voltages in LL rather than LN
                #     voltages_real, voltages_imag = pol2cart(self.voltages_mag / np.sqrt(3), self.voltages_angle)
                #     voltages_real_wls = voltages_real.tolist()
                #     voltages_imag_wls = voltages_imag.tolist()
                #
                #     logger.info(f'self.voltages_real from wls = {voltages_real_wls}')
                #     logger.info(f'self.voltages_imag from wls = {voltages_imag_wls}')
                #
                #     self.voltages_real = voltages_real_wls
                #     self.voltages_imag = voltages_imag_wls
                #
                #     # self.voltages_real = LabelledArray.parse_obj(self.sub_voltages_real.json)
                #     # logger.info(f'Subscribed REAL Voltages Received')
                #
                #     # self.voltages_imag = LabelledArray.parse_obj(self.sub_voltages_imag.json)
                #     # logger.info(f'Subscribed Imag Voltages Received')
                #     # logger.info(f'self.voltages_real from feeder = {self.voltages_real}')
                #     # logger.info(f'self.voltages_imag from feeder = {self.voltages_imag}')
                #
                #     # self.powers_P = LabelledArray.parse_obj(self.sub_powers_real.json)
                #     self.powers_P = np.array(self.sub_powers_real.json['values'])
                #     logger.info(f'Subscribed Active Power Received')
                #
                #     # self.powers_Q = LabelledArray.parse_obj(self.sub_powers_imag.json)
                #     self.powers_Q = np.array(self.sub_powers_imag.json['values'])
                #     logger.info(f'Subscribed Reactive Power Received')
                #
                #     # self.cap_Q = LabelledArray.parse_obj(self.sub_cap_powers_imag.json)
                #     self.cap_Q = np.array(self.sub_cap_powers_imag.json['values'])
                #     logger.info(f"cap_powers_imag received")
                #     logger.debug(f"{self.cap_Q.tolist()}")
                #
                #     # self.pv_P = LabelledArray.parse_obj(self.sub_pv_powers_real.json)
                #     self.pv_P = np.array(self.sub_pv_powers_real.json['values'])
                #
                #     logger.info(f"sub_pv_powers_real power received")
                #     logger.debug(f"{self.pv_P.tolist()}")
                #
                #     # self.pv_Q = LabelledArray.parse_obj(self.sub_powers_imag.json)
                #     self.pv_Q = np.array(self.sub_powers_imag.json['values'])
                #     logger.info(f"sub_pv_powers_imag  imag received")
                #     logger.info(f"{self.pv_Q.tolist()}")
                #
                #     self.tap_vals = np.array(self.sub_tap_values.json['values'])
                #     logger.info(f"sub_tap_values received")
                #     logger.info(f"tap vals received {self.tap_vals.tolist()}")
                #     opf_grid_utility_scripts.unpack_fdrvals_mats(self)
                #     opf_grid_utility_scripts.unpack_fdrvals_vecs(self)
                #
                #     logger.info(f"all grid quantities received")
                #     logger.info(f"formulating the linear model")
                #     t1 = timeit.default_timer()
                #     opf_grid_utility_scripts.get_sens_matrices(self)
                #     t2 = timeit.default_timer()
                #     logger.info(f'sensitivity matrices obtained in {t2-t1} seconds')
                #     opf_grid_utility_scripts.solve_central_optimization(self)
                #     logger.info("optimization complete passing the optimized variable setpoints to grid federate")
                #
                #
                #     self.opf_flex_powers_real.publish(
                #         LabelledArray(values=list(self.p_flex_load_var_opti), ids=self.flex_info.names, units='W').json())
                #     logger.info(f'powers_real published to feeder')
                #
                #     self.opf_cap_powers_imag.publish(
                #         LabelledArray(values=list(self.cap_value_opti), ids=self.cap_info.names, units='Var').json())
                #     logger.info(f'cap_powers_imag published published to feeder')
                #
                #     self.opf_pv_powers_real.publish(
                #         LabelledArray(values=list(self.p_pv_opti), ids=self.pv_info.names, units='W').json())
                #     logger.info(f'pv_powers_real published to feeder')
                #
                #     self.opf_pv_powers_imag.publish(
                #         LabelledArray(values=list(self.q_pv_opti), ids=self.pv_info.names, units='Var').json())
                #     logger.info(f'pv_powers_imag published to feeder')
                #
                #     logger.info(f"pv names {self.pv_info.names}")
                #     logger.info(f"pv p vals {self.p_pv_opti}")
                #     logger.info(f"pv q vals {self.q_pv_opti}")
                #
                #     self.opf_tap_values.publish(
                #         LabelledArray(values=list(self.xmer_value_opti), ids=self.tap_info.names, units='-').json())
                #     logger.info(f'tap_values published to feeder')

                # else: # dynamic
                #     # dynamic states, which may change
                #     self.voltages_angle = LabelledArray.parse_obj(self.sub_voltages_angle.json)
                #     logger.info(f'Subscribed angle Voltages Received from WLS')
                #     logger.info(f'self.voltages_angle = {self.voltages_angle}')
                #     self.voltages_mag = LabelledArray.parse_obj(self.sub_voltages_mag.json)
                #     logger.info(f'Subscribed mag Voltages Received from WLS')
                #     logger.info(f'self.voltages_mag = {self.voltages_mag}')
                #
                #     voltages_real_wls = self.voltages_angle
                #     voltages_imag_wls = self.voltages_mag
                #
                #
                #     # state estimator is calculating voltages in LL rather than LN
                #     voltages_real, voltages_imag = pol2cart(self.voltages_mag.array/np.sqrt(3), self.voltages_angle.array)
                #     voltages_real_wls.array = voltages_real.tolist()
                #     voltages_imag_wls.array = voltages_imag.tolist()
                #
                #     logger.info(f'self.voltages_real from wls = {voltages_real_wls}')
                #     logger.info(f'self.voltages_imag from wls = {voltages_imag_wls}')
                #
                #     self.voltages_real = voltages_real_wls
                #     self.voltages_imag = voltages_imag_wls
                #     # # dynamic states, coming every 60%15 seconds or some predefined intervals
                #     # self.voltages_real = LabelledArray.parse_obj(self.sub_voltages_real.json)
                #     # logger.info(f'Subscribed REAL Voltages Received')
                #     #
                #     # self.voltages_imag = LabelledArray.parse_obj(self.sub_voltages_imag.json)
                #     # logger.info(f'Subscribed Imag Voltages Received')
                #
                #     self.powers_P = LabelledArray.parse_obj(self.sub_powers_real.json)
                #     logger.info(f'Subscribed Active Power Received')
                #
                #     self.powers_Q = LabelledArray.parse_obj(self.sub_powers_imag.json)
                #     logger.info(f'Subscribed Reactive Power Received')
                #
                #     self.cap_Q = LabelledArray.parse_obj(self.sub_cap_powers_imag.json)
                #     logger.info(f"cap_powers_imag received")
                #
                #     self.pv_P = LabelledArray.parse_obj(self.sub_pv_powers_real.json)
                #     logger.info(f"sub_pv_powers_real power received")
                #
                #     self.pv_Q = LabelledArray.parse_obj(self.sub_pv_powers_imag.json)
                #     logger.info(f"sub_pv_powers_imag  imag received")
                #
                #     self.tap_vals = LabelledArray.parse_obj(self.sub_tap_values.json)
                #     logger.info(f"sub_tap_values received")
                #
                #     opf_grid_utility_scripts.unpack_fdrvals_vecs(self)
                #     logger.info(f"formulating the linear model")
                #     opf_grid_utility_scripts.get_sens_matrices(self)
                #     opf_grid_utility_scripts.solve_central_optimization(self)
                #
                #     self.opf_flex_powers_real.publish(
                #         LabelledArray(array=list(self.p_flex_load_var_opti), unique_ids=self.flex_info.names).json())
                #     logger.info(f'powers_real published to feeder')
                #
                #     self.opf_cap_powers_imag.publish(
                #         LabelledArray(array=list(self.cap_value_opti), unique_ids=self.cap_info.names).json())
                #     logger.info(f'cap_powers_imag published published to feeder')
                #
                #     self.opf_pv_powers_real.publish(
                #         LabelledArray(array=list(self.p_pv_opti), unique_ids=self.pv_info.names).json())
                #     logger.info(f'pv_powers_real published to feeder')
                #
                #     self.opf_pv_powers_imag.publish(
                #         LabelledArray(array=list(self.q_pv_opti), unique_ids=self.pv_info.names).json())
                #     logger.info(f'pv_powers_imag published to feeder')
                #
                #     logger.info(f"pv names {self.pv_info.names}")
                #     logger.info(f"pv p vals {self.p_pv_opti}")
                #     logger.info(f"pv q vals {self.q_pv_opti}")
                #
                #     self.opf_tap_values.publish(
                #         LabelledArray(array=list(self.xmer_value_opti), unique_ids=self.tap_info.names).json())
                #     logger.info(f'tap_values published to feeder')


            # granted_time = h.helicsFederateRequestTime(self.opf_fed, h.HELICS_TIME_MAXTIME)
            # logger.info(f'granted time in the for loop --> {granted_time}')

        # self.destroy()

    def destroy(self):
        "Finalize and destroy the federates"
        h.helicsFederateDisconnect(self.opf_fed)
        print("Federate disconnected")

        h.helicsFederateFree(self.opf_fed)
        h.helicsCloseLibrary()


        
if __name__ == '__main__':
    logger.info(f'in opf federate.py')

    with open("static_inputs.json") as f:
        config = json.load(f)
        # federate_name = config["name"]

    with open("input_mapping.json") as f:
        input_mapping = json.load(f)

    opf_fed = OptimalPowerFlowFederate(config, input_mapping)
    opf_fed.go_opf()
