from mjrl.utils.gym_env import GymEnv
from mjrl.policies.gaussian_linear_lpg_ftw import LinearPolicyLPGFTW
from mjrl.baselines.mlp_baseline import MLPBaseline
from mjrl.algos.npg_cg_ftw import NPGFTW
from mjrl.utils.train_agent import train_agent
import time as timer
import numpy as np
import gym
import pickle
import torch
import os
from mjrl.utils.make_train_plots import make_multitask_train_plots, make_multitask_test_plots

SEED = 50   # initial value, 10 will be added for every iteration
job_name_mtl = 'results/hopper_mtl_bodyparts_exp'
job_name_lpgftw = 'results/hopper_lpgftw_bodyparts_exp'
torch.set_num_threads(5)

# MTL policy
# ==================================

num_tasks = 20
num_seeds = 5
num_cpu = 5

f = open(job_name_mtl+'/env_factors.pickle', 'rb')
size_factors_list = pickle.load(f)
f.close()
f = open(job_name_mtl+'/env_ids.pickle','rb')
env_ids = pickle.load(f)
f.close() 
e_unshuffled = {}
for task_id in range(num_tasks): 
      size_factors = size_factors_list[task_id] 
      env_id = env_ids[task_id]    
      gym.envs.register(
            id=env_id,
            entry_point='gym_extensions.continuous.mujoco.modified_hopper:HopperModifiedBodyPartSizeEnv',
            max_episode_steps=1000,
            reward_threshold=3800.0,
            kwargs=dict(body_parts=['torso_geom','thigh_geom','leg_geom','foot_geom'], size_scales=size_factors)
            )
      e_unshuffled[task_id] = GymEnv(env_id)   # only do the environment here, so different files can create the same tasks

for i in range(num_seeds):
      np.random.seed(SEED)
      torch.manual_seed(SEED)

      job_name_lpgftw_seed = job_name_lpgftw + '/seed_{}'.format(i)

      e = {}
      baseline_mtl = {}   
      task_order = np.random.permutation(num_tasks)
      for task_id in range(num_tasks):
            e[task_id] = e_unshuffled[task_order[task_id]]
            baseline_mtl[task_id] = MLPBaseline(e[task_id].spec, reg_coef=1e-3, batch_size=64, epochs=10, learn_rate=1e-4, use_gpu=True)
            
      policy_mtl = LinearPolicyLPGFTW(e[0].spec, k=1, max_k=5, seed=SEED)
      agent_mtl = NPGFTW(e, policy_mtl, baseline_mtl, normalized_step_size=0.01, seed=SEED, save_logs=True, new_col_mode='max_k')


      for task_id in range(num_tasks):
            ts = timer.time()
            train_agent(job_name=job_name_lpgftw_seed,
                        agent=agent_mtl,
                        seed=SEED,
                        niter=100,
                        gamma=0.995,  
                        gae_lambda=0.97,
                        num_cpu=num_cpu,
                        sample_mode='trajectories',
                        num_traj=50,
                        save_freq=5,
                        evaluation_rollouts=0,
                        task_id=task_id)
            agent_mtl.add_approximate_cost(N=10, 
                  task_id=task_id, 
                  num_cpu=num_cpu)
            iterdir = job_name_lpgftw_seed + '/iterations/task_{}/'.format(task_id)
            os.makedirs(iterdir, exist_ok=True)
            policy_file = open(iterdir + 'policy_updated.pickle', 'wb')
            pickle.dump(agent_mtl.policy, policy_file)
            policy_file.close()

            print("time taken for linear policy training = %f" % (timer.time()-ts))

      f = open(job_name_lpgftw_seed+'/trained_mtl_policy.pickle', 'wb')
      pickle.dump(policy_mtl, f)
      f.close()
      f = open(job_name_lpgftw_seed+'/trained_mtl_baseline.pickle', 'wb')
      pickle.dump(baseline_mtl, f)
      f.close()
      f = open(job_name_lpgftw_seed+'/trained_mtl_alphas.pickle', 'wb')
      pickle.dump(agent_mtl.theta, f)
      f.close()
      f = open(job_name_lpgftw_seed+'/trained_mtl_grads.pickle', 'wb')
      pickle.dump(agent_mtl.grad, f)
      f.close()
      f = open(job_name_lpgftw_seed+'/trained_mtl_hess.pickle', 'wb')
      pickle.dump(agent_mtl.hess, f)
      f.close()
      f = open(job_name_lpgftw_seed+'/task_order.pickle', 'wb')
      pickle.dump(task_order, f)
      f.close()


      make_multitask_train_plots(loggers=agent_mtl.logger, keys=['stoc_pol_mean'], save_loc=job_name_lpgftw_seed+'/logs/')

      mean_test_perf = agent_mtl.test_tasks(test_rollouts=10,
                          num_cpu=num_cpu)
      result = np.mean(list(mean_test_perf.values()))
      print(result)
      make_multitask_test_plots(mean_test_perf, save_loc=job_name_lpgftw_seed+'/')
      result_file = open(job_name_lpgftw_seed + '/results.txt', 'w')
      result_file.write(str(mean_test_perf))
      result_file.close()

      SEED += 10



