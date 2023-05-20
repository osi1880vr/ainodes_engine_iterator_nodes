import os
from qtpy import QtCore
from qtpy import QtWidgets

from ainodes_frontend.base import register_node, get_next_opcode
from ainodes_frontend.base import AiNode, CalcGraphicsNode
from ainodes_frontend.node_engine.node_content_widget import QDMNodeContentWidget
from ainodes_frontend.node_engine.utils import dumpException
from ainodes_frontend import singleton as gs

"""
Always change the name of this variable when creating a new Node
Also change the names of the Widget and Node classes, as well as it's content_label_objname,
it will be used when saving the graphs.
"""

OP_NODE_MANY_PROMPTS = get_next_opcode()


class ManyPromptsWidget(QDMNodeContentWidget):
	def initUI(self):
		self.create_widgets()
		self.create_main_layout()

	def create_widgets(self):
		self.prompt = self.create_text_edit("Prompt")


@register_node(OP_NODE_MANY_PROMPTS)
class ManyPromptsNode(AiNode):
	icon = "ainodes_frontend/icons/base_nodes/in.png"
	op_code = OP_NODE_MANY_PROMPTS
	op_title = "Many Prompts Node"
	content_label_objname = "many_prompts_node"
	category = "Data"
	custom_input_socket_name = ['DONE','LOOP', "DATA", "EXEC"]

	custom_output_socket_name = ['DONE', "DATA", "EXEC"]

	def __init__(self, scene):
		super().__init__(scene, inputs=[1, 1, 6, 1], outputs=[1, 6, 1])

	def initInnerClasses(self):
		self.content = ManyPromptsWidget(self)
		self.grNode = CalcGraphicsNode(self)
		self.grNode.width = 340
		self.grNode.height = 500
		self.content.setMinimumWidth(340)
		self.content.setMinimumHeight(500)
		self.content.eval_signal.connect(self.evalImplementation)
		self.iteration_lenght = 0
		self.iteration_step = 0
		self.done = False
		self.prompts = []
		self.stop_top_iterator = False

	def get_conditioning(self, prompt="", progress_callback=None):

		"""if gs.loaded_models["loaded"] == []:
			for node in self.scene.nodes:
				if isinstance(node, TorchLoaderNode):
					node.evalImplementation()
					#print("Node found")"""

		c = gs.models["clip"].encode(prompt)
		uc = {}
		return [[c, uc]]

	@QtCore.Slot()
	def evalImplementation_thread(self):
		self.busy = True
		data = None


		if len(self.getInputs(2)) > 0:
			data_node, index = self.getInput(2)
			data = data_node.getOutput(index)
		else:
			self.stop_top_iterator = True

		if data and 'loop_done' in data:
			if data['loop_done'] == True:
				self.stop_top_iterator = True


		if self.iteration_lenght == 0:
			self.prompts = self.content.prompt.toPlainText().split('\n')
			self.iteration_lenght = len(self.prompts) - 1

		prompt = self.prompts[self.iteration_step]
		print(prompt)
		#result = [self.get_conditioning(prompt=prompt)]
		result = 'test'
		self.iteration_step += 1
		if self.iteration_step > self.iteration_lenght:
			self.done = True
			if not data:
				data = {}
			data['loop_done'] = True
		"""
		Do your magic here, to access input nodes data, use self.getInputData(index),
		this is inherently threaded, so returning the value passes it to the onWorkerFinished function,
		it's super call makes sure we clean up and safely return.

		Inputs and Outputs are listed from the bottom of the node.
		"""
		return result, data

	@QtCore.Slot(object)
	def onWorkerFinished(self, result):
		super().onWorkerFinished(None)
		self.setOutput(1, result[1])
		self.getInput(0)
		if self.done:
			self.done = False
			self.iteration_step = 0
			if not self.stop_top_iterator:
				self.executeChild(0) # get the next step from the maybe top iterator if there is any
			else:
				self.executeChild(2) # make the very last step happen
		else:
			self.executeChild(2)