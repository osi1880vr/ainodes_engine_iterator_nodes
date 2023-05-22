from qtpy import QtCore
from ainodes_frontend.base import register_node, get_next_opcode
from ainodes_frontend.base import AiNode, CalcGraphicsNode
from ainodes_frontend.node_engine.node_content_widget import QDMNodeContentWidget
from ainodes_frontend import singleton as gs

"""
Always change the name of this variable when creating a new Node
Also change the names of the Widget and Node classes, as well as it's content_label_objname,
it will be used when saving the graphs.
"""

OP_NODE_LOOP_ITERATORS = get_next_opcode()


class LoopIteratorsWidget(QDMNodeContentWidget):
	set_checked_signal = QtCore.Signal()
	def initUI(self):
		self.create_widgets()
		self.create_main_layout()

	def create_widgets(self):
		self.checkbox = self.create_check_box("Kepp looping")

@register_node(OP_NODE_LOOP_ITERATORS)
class LoopIteratorsNode(AiNode):
	icon = "ainodes_frontend/icons/base_nodes/in.png"
	op_code = OP_NODE_LOOP_ITERATORS
	op_title = "Iterator Loop Counter Node"
	content_label_objname = "loop_iterators_node"
	category = "Iterators"
	custom_output_socket_name = ["FINAL_EXEC", "LOOP"]

	def __init__(self, scene):
		super().__init__(scene, inputs=[6, 1], outputs=[1,1])


	def initInnerClasses(self):
		self.content = LoopIteratorsWidget(self)
		self.grNode = CalcGraphicsNode(self)
		self.grNode.width = 240
		self.grNode.height = 150
		self.content.setMinimumWidth(240)
		self.content.setMinimumHeight(80)
		self.content.eval_signal.connect(self.evalImplementation)
		self.counter = 0
		self.content.set_checked_signal.connect(self.set_checked)
		self.content.set_checked_signal.emit()

	@QtCore.Slot()
	def set_checked(self):
		self.content.checkbox.setChecked = True

	@QtCore.Slot()
	def evalImplementation_thread(self):
		data = self.getInputData(0)
		result = 1

		if data is not None:
			prompt_counts = []
			for key, value in data.items():

				print(key)

				if "iterator" in key:
					prompt_counts.append(data[key])

			# Multiply the items in the prompt_counts list
			for item in prompt_counts:
				result *= item

		print(self.counter, result)
		return result


	@QtCore.Slot(object)
	def onWorkerFinished(self, result):
		super().onWorkerFinished(None)
		if self.content.checkbox.isChecked:
			self.counter += 1
			if result is not None:
				if self.counter > result - 2:
					self.executeChild(0)
					self.counter = 0
				if self.counter < result - 1:
					self.executeChild(1)
			else:
				self.executeChild(1)
		else:
			gs.should_run = None
