import os


from qtpy import QtCore
from qtpy import QtWidgets

from custom_nodes.ainodes_engine_base_nodes.ainodes_backend.model_loader import ModelLoader
from custom_nodes.ainodes_engine_base_nodes.ainodes_backend import torch_gc
from custom_nodes.ainodes_engine_base_nodes.ainodes_backend.sd_optimizations.sd_hijack import valid_optimizations

from ainodes_frontend.base import register_node, get_next_opcode
from ainodes_frontend.base import AiNode, CalcGraphicsNode
from ainodes_frontend.node_engine.node_content_widget import QDMNodeContentWidget
from ainodes_frontend.node_engine.utils import dumpException
from ainodes_frontend import singleton as gs
from pydispatch import dispatcher

"""
Always change the name of this variable when creating a new Node
Also change the names of the Widget and Node classes, as well as it's content_label_objname,
it will be used when saving the graphs.
"""

OP_NODE_MANY_MODELS = get_next_opcode()


class ManyModelsWidget(QDMNodeContentWidget):
    show_iteration_signal = QtCore.Signal(str)
    add_config_signal = QtCore.Signal()
    def initUI(self):
        self.create_widgets()
        self.create_main_layout()

    def create_widgets(self):
        checkpoint_folder = gs.checkpoints
        checkpoint_files = [f for f in os.listdir(checkpoint_folder) if
                            f.endswith(('.ckpt', '.pt', '.bin', '.pth', '.safetensors'))]
        self.dropdown = self.create_combo_box(checkpoint_files, "Models")
        if checkpoint_files == []:
            self.dropdown.addItem("Please place a model in models/checkpoints")
            print(f"TORCH LOADER NODE: No model file found at {os.getcwd()}/models/checkpoints,")
            print(f"TORCH LOADER NODE: please download your favorite ckpt before Evaluating this node.")

        config_folder = "models/configs"
        config_files = [f for f in os.listdir(config_folder) if f.endswith((".yaml"))]
        config_files = sorted(config_files, key=str.lower)
        self.config_dropdown = self.create_combo_box(config_files, "Configs")
        self.config_dropdown.setCurrentText("v1-inference_fp16.yaml")
        vae_folder = gs.vae
        vae_files = [f for f in os.listdir(vae_folder) if f.endswith(('.ckpt', '.pt', '.bin', '.pth', '.safetensors'))]
        vae_files = sorted(vae_files, key=str.lower)
        self.vae_dropdown = self.create_combo_box(vae_files, "Vae")
        self.vae_dropdown.addItem("default")
        self.vae_dropdown.setCurrentText("default")

        self.optimization = self.create_combo_box(valid_optimizations, "LDM Optimization")

        self.force_reload = self.create_check_box("Force Reload")

        self.add_button = QtWidgets.QPushButton("Add Model Config")
        self.create_button_layout([self.add_button])
        self.steps = self.create_text_edit("Values")

        self.actual_iteration_value = self.create_line_edit("Actual Value")


@register_node(OP_NODE_MANY_MODELS)
class ManyModelsNode(AiNode):
    icon = "ainodes_frontend/icons/base_nodes/in.png"
    op_code = OP_NODE_MANY_MODELS
    op_title = "Many Models Node"
    content_label_objname = "many_models_node"
    category = "Iterators"
    custom_input_socket_name = ['DONE','LOOP', "DATA", "EXEC"]

    custom_output_socket_name = ['DONE', "DATA", "EXEC"]

    def __init__(self, scene):
        super().__init__(scene, inputs=[1, 1, 6, 1], outputs=[1, 6, 1])
        self.loader = ModelLoader()

    def initInnerClasses(self):
        self.content = ManyModelsWidget(self)
        self.grNode = CalcGraphicsNode(self)
        self.grNode.width = 340
        self.grNode.height = 400
        self.content.setMinimumWidth(340)
        self.content.setMinimumHeight(300)
        self.content.eval_signal.connect(self.evalImplementation)
        self.reset_handler('init')
        self.reset = False
        self.reset_signal = 'reset_iterator'
        dispatcher.connect(self.reset_handler, signal=self.reset_signal)
        self.content.show_iteration_signal.connect(self.set_actual_value)
        self.content.add_config_signal.connect(self.add_config_value)
        self.content.add_button.clicked.connect(self.add_config)

    #@QtCore.Slot()
    def reset_handler(self, sender):
        self.reset = True
        self.iteration_lenght = 0
        self.iteration_step = 0
        self.done = False
        self.all_done = False
        self.prompts = []
        self.stop_top_iterator = False
        self.last_optimization = None
        self.reset = False

    #@QtCore.Slot(str)
    def set_actual_value(self, value):
        self.content.actual_iteration_value.setText(value)


    def add_config(self):
        self.content.add_config_signal.emit()

    #@QtCore.Slot()
    def add_config_value(self):
        current_text = self.content.steps.toPlainText()
        if current_text != '':
            self.content.steps.setText(
                f'{current_text}\n{self.content.dropdown.currentText()},{self.content.config_dropdown.currentText()},{self.content.vae_dropdown.currentText()},{self.content.optimization.currentText()}')
        else:
            self.content.steps.setText(
                f'{self.content.dropdown.currentText()},{self.content.config_dropdown.currentText()},{self.content.vae_dropdown.currentText()},{self.content.optimization.currentText()}')

    def calc_next_step(self):
        self.iteration_step += 1
        if self.iteration_step > self.iteration_lenght:
            self.done = True

    def clean_sd(self):
        gs.loaded_loras = []
        if "sd" in gs.models:
            try:
                gs.models["sd"].cpu()
            except:
                pass
            del gs.models["sd"]
            gs.models["sd"] = None
            torch_gc()
        if "inpaint" in gs.models:
            try:
                gs.models["inpaint"].cpu()
            except:
                pass
            del gs.models["inpaint"]
            gs.models["inpaint"] = None
            torch_gc()

    #@QtCore.Slot()
    def evalImplementation_thread(self):
        while self.reset:
            pass
        self.busy = True
        data = None
        result = None

        try:
            if not self.all_done:

                if self.iteration_step == -1:
                    return result, data

                # care for the loops to work as such, no node fucntionality yet
                if len(self.getInputs(2)) > 0: # get data from a maybe top loop
                    data_node, index = self.getInput(2)
                    data = data_node.getOutput(index)
                    data = data.copy()
                else:
                    self.stop_top_iterator = True # if none make sure we dont trigger done

                if not data:
                    data = {}


                # here the internal magic starts with finding out how many steps the loop will have
                if self.iteration_lenght == 0:
                    self.steps = self.content.steps.toPlainText().split('\n')
                    self.iteration_lenght = len(self.steps) - 1

                value = self.steps[self.iteration_step]
                self.content.show_iteration_signal.emit(value)

                model_name, config_name, vae_name, optimization = value.split(',')

                # if optimization has changed from last iteration we have to force a reload of model
                if self.last_optimization and self.last_optimization != optimization:
                    self.clean_sd()


                inpaint = True if "inpaint" in model_name else False
                m = "sd_model" if not inpaint else "inpaint"
                if gs.loaded_sd != model_name or self.content.force_reload.isChecked() == True:
                    self.clean_sd()
                    self.loader.load_model(model_name, config_name, inpaint, optimization)
                    gs.loaded_sd = model_name
                    self.setOutput(0, model_name)
                if vae_name != 'default':
                    model = vae_name
                    self.loader.load_vae(model)
                    gs.loaded_vae = model
                else:
                    gs.loaded_vae = 'default'
                if gs.loaded_vae != vae_name:
                    model = vae_name
                    self.loader.load_vae(model)
                    gs.loaded_vae = model
                else:
                    self.markDirty(False)
                    self.markInvalid(False)
                    self.grNode.setToolTip("")





                if data and 'loop_done' in data: # if the top loop tels us its done with its loop make sure no more done is send
                    if data['loop_done'] == True:
                        self.stop_top_iterator = True
                        data['loop_done'] = False

                self.calc_next_step()

            """
            Do your magic here, to access input nodes data, use self.getInputData(index),
            this is inherently threaded, so returning the value passes it to the onWorkerFinished function,
            it's super call makes sure we clean up and safely return.
    
            Inputs and Outputs are listed from the bottom of the node.
            """

            if data is not None:
            #Before we return the data, we make sure, the current prompt count is in it with the node's unique id
                data[f"iterator_{self.getID(0)}"] = len(self.steps)
        except Exception as e:
            print(e)

        return result, data

    #@QtCore.Slot(object)
    def onWorkerFinished(self, result):
        self.markDirty(False)
        self.markInvalid(False)
        self.grNode.setToolTip("")

        #super().onWorkerFinished(None)
        self.busy = False
        print(result[1])
        self.setOutput(1, result[1])
        self.getInput(0)

        if self.done: # if this loop is finished we may have to restart if we are in a larger stacked loop

            if not self.stop_top_iterator: # if the top loop is not yet done we trigger him

                if self.iteration_step > 0: # this is the last step of this iteration, we still have to trigger the rest of the process
                    self.iteration_step = -1 # but for when we come back for this we know we have to trigger top loop to get a new value from there
                    self.executeChild(2)
                else:
                    self.done = False     # we are back from the last step process now we trigger top loop
                    self.iteration_step = 0
                    self.executeChild(0)

            # get the next step from the maybe top iterator if there is any
            else:
                if not self.all_done:  # if we self are not done we trigger the next
                    self.all_done = True
                    if self.stop_top_iterator is True:
                        result[1]['loop_done'] = True
                    self.executeChild(2) # make the very last step happen
        else:
            if not self.all_done:
                self.executeChild(2)