# 作者代码与许可

本目录保留公开作者实现及原始许可证。课程封装位于 `vision/experiments/`；模型推理、后处理、资源加载与工程兼容性修改应结合来源清单及实际 Git 差异审阅。包含作者代码不等于课程实验已经运行或通过验收。

| 目录 | 作者来源与固定提交 | 许可 | 课程使用方式 |
| --- | --- | --- | --- |
| `cirtorch/` | [cnn-imageretrieval-pytorch](https://github.com/filipradenovic/cnnimageretrieval-pytorch)，`1e66a417afa2247edde6d35f3a9a2a465778a3a8` | MIT；版权2016–2019 VRG, CTU Prague | 使用作者GeM和L2归一化函数；课程adapter重建相同VGG16卷积骨干并严格加载检索权重，避免下载默认ImageNet权重。现代Pillow以LANCZOS对应原ANTIALIAS。平均/最大池化仅作同一已训练骨干的推理对照。 |
| `visil/` | [ViSiL PyTorch分支](https://github.com/MKLab-ITI/visil/tree/pytorch)，`5751de6d7fdd48098b35c694aa250f2f1dad6a9f` | Apache-2.0 | 作者完整区域特征、PCA、attention、帧匹配、2D CNN、截断及有向Chamfer流程。封装将公开权重加载映射到本地文件，设置`symmetric=False`；不将单帧余弦替代主模型。 |
| `dsnet/` | [DSNet](https://github.com/li-plus/DSNet)，`1804176e2e8b57846beb063667448982273fca89` | MIT；KTS另保留其目录许可证 | 使用anchor-free预训练模型与官方TVSum划分。课程后处理以精确整数动态规划替代旧ORTools背包接口，按NMS0.4、原帧分数恢复、分段均值及预算选择运行；具体实现见summary.py。 |

保留各目录 `LICENSE`、原作者署名、README及子组件许可证；转载和提交时不得移除。作者仓库版本与下载资源的hash记录于 `vision/manifests/`，ViSiL另有 `COURSE_PROVENANCE.json`。课程新增代码和作者原实现应分别说明，不能将原实现全部声称为本人编写。

数据和预训练权重的使用条款不因代码许可证自动变成MIT或Apache-2.0。COIL-100、TVSum、DSNet特征和各预训练权重按其公开来源引用，来源页或档内未发现独立许可证文本的项目在清单中如实标注。大型资源从匿名公开URL下载到配置的资源目录，不包含于代码提交包。

本目录可随必要代码和许可证选择性打包；无需包含嵌套`.git`元数据、下载缓存、数据集、权重或环境。主项目的版本记录与来源清单足以说明固定作者提交。不得通过清理或删除原文件来制作提交包。
