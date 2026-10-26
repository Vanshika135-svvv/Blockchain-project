import hre from "hardhat";

async function main() {
  console.log("Starting deployment of EWasteTracker...");

  const EWasteTracker = await hre.ethers.getContractFactory("EWasteTracker");
  const tracker = await EWasteTracker.deploy();
  await tracker.waitForDeployment();

  const deployedAddress = await tracker.getAddress();

  console.log("----------------------------------------------------");
  console.log(`EWasteTracker successfully deployed to: ${deployedAddress}`);
  console.log("----------------------------------------------------");
}

main().catch((error) => {
  console.error("Deployment failed:", error);
  process.exitCode = 1;
});