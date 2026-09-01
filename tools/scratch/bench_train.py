import os
import time
import yaml
import torch


with open("PlanT/config/config.yaml") as f:
    cfg = yaml.safe_load(f)
with open("PlanT/config/model/PlanT.yaml") as f:
    cfg["model"] = yaml.safe_load(f)
cfg["visualize"] = False
cfg["gpus"] = 1
cfg["model"]["training"]["augment"] = False
cfg["model"]["training"]["augment_parked"] = False
cfg["model"]["training"]["input_ego_speed"] = True
cfg["model"]["training"]["input_representation"] = "exact"
cfg["model"]["training"]["exclude_towns"] = ["Town05"]
for k in ["include_towns", "exclude_scenarios", "include_scenarios"]:
    cfg["model"]["training"][k] = []


class DictAsMember(dict):
    def __getattr__(self, n):
        v = self[n]
        return DictAsMember(v) if isinstance(v, dict) else v


from dataset import PlanTDataset, generate_batch
from lit_module import LitHFLM
from torch.utils.data import DataLoader
from omegaconf import OmegaConf

BATCH = int(os.environ.get("BATCH", "128"))
NW = int(os.environ.get("NW", "4"))

cfg_oc = OmegaConf.create(cfg)

t0 = time.time()
ds = PlanTDataset(os.environ["DS"] + "/data", cfg_oc)
print(f"dataset init: {time.time()-t0:.1f}s, len={len(ds)}", flush=True)

loader = DataLoader(ds, shuffle=True, pin_memory=True, batch_size=BATCH,
                    collate_fn=generate_batch, num_workers=NW)

# ---- data loading throughput ----
t0 = time.time()
nb = 0
for i, batch in enumerate(loader):
    if i >= 12:
        break
    nb += 1
dt = time.time() - t0
print(f"data loading: {nb} batches in {dt:.2f}s -> {nb/dt:.2f} batch/s "
      f"({nb*BATCH/dt:.0f} samples/s)", flush=True)

# ---- compute throughput ----
torch.set_float32_matmul_precision("high")
model = LitHFLM(cfg=cfg_oc).cuda()
model.train()
opt = torch.optim.Adam(model.parameters(), lr=1e-4)

t0 = time.time()
niters = 8
for i, batch in enumerate(loader):
    if i >= niters:
        break
    b = {k: (v.cuda() if torch.is_tensor(v) else v) for k, v in batch.items()}
    opt.zero_grad()
    loss = model.training_step(b, i)
    loss.backward()
    opt.step()
compute_dt = time.time() - t0
print(f"compute (fwd+bwd+step): {niters} iters in {compute_dt:.2f}s -> {niters/compute_dt:.2f} iter/s "
      f"({niters*BATCH/compute_dt:.0f} samples/s)", flush=True)

# ---- extrapolation ----
steps_per_epoch = len(ds) // BATCH
per_step = compute_dt / niters
secs = steps_per_epoch * per_step
print(f"\nsteps/epoch={steps_per_epoch} len={len(ds)}")
print(f"estimate per epoch (compute-bound): {secs:.0f}s = {secs/60:.1f} min")
print(f"estimate for 5 epochs: {5*secs/60:.1f} min = {5*secs/3600:.2f} h")
