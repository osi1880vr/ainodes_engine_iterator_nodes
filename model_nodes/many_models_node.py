import os


from qtpy import QtCore
from qtpy import QtWidgets

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
    def initUI(self):
        self.create_widgets()
        self.create_main_layout()

    def create_widgets(self):
        checkpoint_folder = gs.checkpoints
        checkpoint_files = [f for f in os.listdir(checkpoint_folder) if
                            f.endswith(('.ckpt', '.pt', '.bin', '.pth', '.safetensors'))]
        self.steps = self.create_list_view("Values")
        self.steps.addActions(checkpoint_files)
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

    @QtCore.Slot()
    def reset_handler(self, sender):
        self.reset = True
        self.iteration_lenght = 0
        self.iteration_step = 0
        self.done = False
        self.all_done = False
        self.prompts = []
        self.stop_top_iterator = False
        self.reset = False

    @QtCore.Slot(str)
    def set_actual_value(self, value):
        self.content.actual_iteration_value.setText(value)


    def calc_next_step(self):
        self.iteration_step += 1
        if self.iteration_step > self.iteration_lenght:
            self.done = True



    @QtCore.Slot()
    def evalImplementation_thread(self):
        while self.reset:
            pass
        self.busy = True
        data = None
        result = None

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

            current_selection = self.content.dropdown.currentText()

            if current_selection in ['steps', 'seed']:
                data[current_selection] = int(value)
            elif current_selection in ['cfg']:
                data[current_selection] = float(value)
            else:
                data[current_selection] = str(value)



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

        return result, data

    @QtCore.Slot(object)
    def onWorkerFinished(self, result):
        super().onWorkerFinished(None)
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