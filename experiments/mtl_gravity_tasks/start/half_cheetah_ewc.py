'''
Measure performance after updating L at the end
of training each task
'''

from mjrl.utils.gym_env import GymEnv
# from mjrl.policies.gaussian_linear_ewc import LinearPolicyEWC   # use this instead for not shared version
from mjrl.policies.gaussian_linear import LinearPolicy
from mjrl.algos.npg_cg_ewc import NPGEWC
import numpy as np
import gym
import pickle
import torch
import os

SEED = 50  # initial value, 10 will be added for every iteration
job_name_mtl = 'results/halfcheetah_mtl_gravity_exp'
job_name_ewc = 'results/ewc_std_shared_notscaled/halfcheetah_ewc_gravity_exp'

# MTL policy
# ==================================

num_tasks = 20
num_seeds = 5
num_cpu = 5

f = open(job_name_mtl+'/env_factors.pickle', 'rb')
gravity_factors = pickle.load(f)
f.close()
f = open(job_name_mtl+'/env_ids.pickle','rb')
env_ids = pickle.load(f)
f.close() 
e_unshuffled = {}
for task_id in range(num_tasks): 
      gravity_factor = gravity_factors[task_id] 
      env_id = env_ids[task_id]    
      gym.envs.register(
            id=env_id,
            entry_point='gym_extensions.continuous.mujoco.modified_half_cheetah:HalfCheetahGravityEnv',
            max_episode_steps=1000,
            reward_threshold=3800.0,
            kwargs=dict(gravity=-gravity_factor*9.81)
            )
      e_unshuffled[task_id] = GymEnv(env_id)   # only do the environment here, so different files can create the same tasks

for i in range(num_seeds):
      np.random.seed(SEED)
      torch.manual_seed(SEED)

      job_name_ewc_seed = job_name_ewc + '/seed_{}'.format(i)

      f = open(job_name_ewc_seed+'/task_order.pickle', 'rb')
      task_order = pickle.load(f)
      f.close()
      e = {}
      for task_id in range(num_tasks):
            e[task_id] = e_unshuffled[task_order[task_id]]

      baseline_mtl = {}

      forward_transfer_results = {}
      for t in range(num_tasks):
            job_name_ewc_seed = job_name_ewc + '/seed_{}'.format(i)
            f = open(job_name_ewc_seed + '/iterations/task_{}/'.format(t) +  'policy_0.pickle', 'rb')
            policy_mtl = pickle.load(f)
            f.close()
            f = open(job_name_ewc_seed + '/iterations/task_{}/'.format(t) +  'baseline_0.pickle', 'rb')
            baseline_mtl[t] = pickle.load(f)
            f.close()

            agent_mtl = NPGEWC(e, policy_mtl, baseline_mtl, ewc_lambda=1e-6, scaled_lambda=False, normalized_step_size=1, seed=SEED, save_logs=True)

            mean_test_perf = agent_mtl.test_tasks(test_rollouts=10,
                                num_cpu=num_cpu,
                                task_ids=np.array([t]))

            forward_transfer_results = {**forward_transfer_results, **mean_test_perf}

      result_file = open(job_name_ewc_seed + '/start_results.txt', 'w')
      result_file.write(str(forward_transfer_results))
      result_file.close()

      SEED += 10



