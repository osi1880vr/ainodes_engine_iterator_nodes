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

OP_NODE_RESET_ITERATORS = get_next_opcode()


class ResetIteratorsWidget(QDMNodeContentWidget):
	def initUI(self):
		self.create_main_layout()



@register_node(OP_NODE_RESET_ITERATORS)
class ResetIteratorsNode(AiNode):
	icon = "ainodes_frontend/icons/base_nodes/v2/loops.png"
	op_code = OP_NODE_RESET_ITERATORS
	op_title = "Reset Iterators Node"
	content_label_objname = "reset_iterators_node"
	category = "Iterators"
	custom_input_socket_name = ["EXEC"]

	custom_output_socket_name = ["EXEC"]

	def __init__(self, scene):
		super().__init__(scene, inputs=[1], outputs=[1])

	def initInnerClasses(self):
		self.content = ResetIteratorsWidget(self)
		self.grNode = CalcGraphicsNode(self)
		self.grNode.width = 240
		self.grNode.height = 100
		self.content.setMinimumWidth(240)
		self.content.setMinimumHeight(100)
		self.content.eval_signal.connect(self.evalImplementation)
		self.reset_signal = 'reset_iterator'


	#@QtCore.Slot()
	def evalImplementation_thread(self):
		self.busy = True
		dispatcher.send(signal=self.reset_signal, sender="Iterator reset")
		return None

	#@QtCore.Slot(object)
	def onWorkerFinished(self, result):
		self.busy = False

		#super().onWorkerFinished(None)
		self.executeChild(0)