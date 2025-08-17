from steps.lib.dataloaders.survey import load_incentives
shape = load_incentives().shape
print("✅ Step 5 OK — Analysis kann Dataloader importieren. incentives:", shape)
