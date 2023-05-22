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

OP_NODE_MANY_PROMPTS = get_next_opcode()


class ManyPromptsWidget(QDMNodeContentWidget):
	def initUI(self):
		self.create_widgets()
		self.create_main_layout()

	def create_widgets(self):
		self.prompt = self.create_text_edit("Prompt")
		self.actual_prompt = self.create_line_edit("Actual Prompt")


@register_node(OP_NODE_MANY_PROMPTS)
class ManyPromptsNode(AiNode):
	icon = "ainodes_frontend/icons/base_nodes/in.png"
	op_code = OP_NODE_MANY_PROMPTS
	op_title = "Many Prompts Node"
	content_label_objname = "many_prompts_node"
	category = "Iterators"
	custom_input_socket_name = ['DONE','LOOP', "DATA", "EXEC"]

	custom_output_socket_name = ['DONE', "DATA", "EXEC"]

	def __init__(self, scene):
		super().__init__(scene, inputs=[1, 1, 6, 1], outputs=[1, 6, 1])

	def initInnerClasses(self):
		self.content = ManyPromptsWidget(self)
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


	def reset_handler(self, sender):
		self.reset = True
		self.iteration_lenght = 0
		self.iteration_step = 0
		self.done = False
		self.all_done = False
		self.prompts = []
		self.stop_top_iterator = False
		self.reset = False

	def get_conditioning(self, prompt="", progress_callback=None):

		"""if gs.loaded_models["loaded"] == []:
			for node in self.scene.nodes:
				if isinstance(node, TorchLoaderNode):
					node.evalImplementation()
					#print("Node found")"""

		c = gs.models["clip"].encode(prompt)
		uc = {}
		return [[c, uc]]

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
			print('input ', data)

			# here the internal magic starts with finding out how many steps the loop will have
			if self.iteration_lenght == 0:
				self.prompts = self.content.prompt.toPlainText().split('\n')
				self.iteration_lenght = len(self.prompts) - 1

			prompt = self.prompts[self.iteration_step]
			self.content.actual_prompt.setText(prompt)

			if 'prompt' in data:
				data['prompt'] = f"{data['prompt']} {prompt}"
			else:
				data['prompt'] = prompt

			print('output ', data['prompt'])


			if data and 'loop_done' in data: # if the top loop tels us its done with its loop make sure no more done is send
				if data['loop_done'] == True:
					self.stop_top_iterator = True
					data['loop_done'] = False


			#result = [self.get_conditioning(prompt=prompt)]
			result = 'test'
			self.calc_next_step()

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



		if self.done: # if this loop is finished we may have to restart if we are in a larger stacked loop

			if not self.stop_top_iterator: # if the top loop is not yet done we trigger him

				if self.iteration_step > 0: # this is the last step of this iteration, we still have to trigger the rest of the process
					self.iteration_step = -1 # but for when we come back for this we know we have to trigger top loop to get a new value from there
					print(result[1]['prompt'])
					self.executeChild(2)
				else:
					self.done = False     # we are back from the last step process now we trigger top loop
					self.iteration_step = 0
					self.executeChild(0)

			# get the next step from the maybe top iterator if there is any
			else:
				if not self.all_done:  # if we self are not done we trigger the next
					self.all_done = True
					print(result[1]['prompt'])
					if self.stop_top_iterator is True:
						result[1]['loop_done'] = True
					self.executeChild(2) # make the very last step happen
		else:
			if not self.all_done:
				print(result[1]['prompt'])
				self.executeChild(2)