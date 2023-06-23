'''
Implement and solve the following nonlinear program:
decide q_0 ... q_T \in R^NQxT
minimizing   sum_t || q_t - q_t+1 ||**2 + || log( M(q_T)^-1 M^* ||^2 
so that q_0 = robot.q0
with M(q) \in SE(3) the placement of the robot end-effector, and M^* the target.

The following tools are used:
- the ur10 model (loaded by example-robot-data)
- pinocchio.casadi for writing the problem and computing its derivatives
- the IpOpt solver wrapped in casadi
- the meshcat viewer
'''

import time
import unittest
import numpy as np
import pinocchio as pin
import casadi
from pinocchio import casadi as cpin
import example_robot_data as robex
from scipy.optimize import fmin_bfgs
from numpy.linalg import norm

from utils.meshcat_viewer_wrapper import MeshcatVisualizer

# Change numerical print
pin.SE3.__repr__=pin.SE3.__str__
np.set_printoptions(precision=2, linewidth=300, suppress=True,threshold=1e6)

### HYPER PARAMETERS
Mtarget = pin.SE3(pin.utils.rotate('y', 3), np.array([-0.5, 0.1, 0.2]))  # x,y,z
q0 = np.array([0, -3.14 / 2, 0, 0, 0, 0])
T = 10
w_run = .1
w_term = 1

# --- Load robot model
robot = robex.load('ur5')
robot.q0 = q0
# Open the viewer
viz = MeshcatVisualizer(robot)
viz.display(robot.q0)
time.sleep(.3)
print("Let's go to pdes ... with casadi")

# The pinocchio model is what we are really interested by.
model = robot.model
data = model.createData()
idTool = model.getFrameId('tool0')

# --- Add box to represent target
# Add a vizualization for the target
boxID = "world/box"
viz.addBox(boxID, [.05, .1, .2], [1., .2, .2, .5])
# %jupyter_snippet 1
# Add a vizualisation for the tip of the arm.
tipID = "world/blue"
viz.addBox(tipID, [.08] * 3, [.2, .2, 1., .5])
def displayScene(q,dt=1e-1):
    '''
    Given the robot configuration, display:
    - the robot
    - a box representing idTool
    - a box representing Mtarget
    '''
    pin.framesForwardKinematics(model,data,q)
    M = data.oMf[idTool]
    viz.applyConfiguration(boxID, Mtarget)
    viz.applyConfiguration(tipID, M)
    viz.display(q)
    time.sleep(dt)
def displayTraj(qs,dt=1e-2):
    for q in qs[1:]:
        displayScene(q,dt=dt)

# --- Casadi helpers
cmodel = cpin.Model(model)
cdata = cmodel.createData()

cq = casadi.SX.sym("x",model.nq,1)
cpin.framesForwardKinematics(cmodel,cdata,cq)
pos_tool = casadi.Function('ptool', [cq], [ cdata.oMf[idTool].translation ])
error_tool = casadi.Function('etool', [cq],
                             [ cpin.log6(cdata.oMf[idTool].inverse() * cpin.SE3(Mtarget)).vector ])

### PROBLEM
opti = casadi.Opti()
var_qs = [ opti.variable(model.nq) for t in range(T+1) ]
totalcost = 0
opti.subject_to(var_qs[0] == robot.q0)

for t in range(T):
    totalcost += w_run * casadi.sumsqr( var_qs[t] - var_qs[t+1] )
totalcost += w_term * casadi.sumsqr( error_tool(var_qs[T]) )

### SOLVE
opti.minimize(totalcost)
opti.solver("ipopt") # set numerical backend
opti.callback(lambda i: displayScene(opti.debug.value(var_qs[-1])))

# Caution: in case the solver does not converge, we are picking the candidate values
# at the last iteration in opti.debug, and they are NO guarantee of what they mean.
try:
    sol = opti.solve_limited()
    sol_qs = [ opti.value(var_q) for var_q in var_qs ]
except:
    print('ERROR in convergence, plotting debug info.')
    sol_qs = [ opti.debug.value(var_q) for var_q in var_qs ]

print("***** Display the resulting trajectory ...")
displayScene(robot.q0,1)
displayTraj(sol_qs)

