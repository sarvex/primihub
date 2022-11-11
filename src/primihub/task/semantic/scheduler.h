/*
 Copyright 2022 Primihub

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

      https://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
 */

#ifndef SRC_PRIMIHUB_TASK_SEMANTIC_SCHEDULER_H_
#define SRC_PRIMIHUB_TASK_SEMANTIC_SCHEDULER_H_

#include <algorithm>
#include <cmath>
#include <iostream>
#include <memory>
#include <numeric>
#include <string>
#include <thread>
#include <vector>

#include "src/primihub/protos/worker.grpc.pb.h"
#include "src/primihub/service/dataset/service.h"
#include "src/primihub/util/log_wrapper.h"

using primihub::rpc::Node;
using primihub::rpc::PushTaskReply;
using primihub::rpc::PushTaskRequest;
using primihub::rpc::VMNode;
using primihub::service::DatasetWithParamTag;

namespace primihub::task {
#define V_VLOG(level) \
   VLOG_WRAPPER(level, platform(), job_id(), task_id())

#define LOG_INFO() \
   LOG_INFO_WRAPPER(platform(), job_id(), task_id())

#define LOG_WARNING() \
   LOG_WARNING_WRAPPER(platform(), job_id(), task_id())

#define LOG_ERROR() \
   LOG_ERROR_WRAPPER(platform(), job_id(), task_id())

using PeerDatasetMap = std::map<std::string, std::vector<DatasetWithParamTag>>;

class VMScheduler {
  public:
    VMScheduler(const std::string &node_id,
                 bool singleton)
        : node_id_(node_id),
          singleton_(singleton) {}

    virtual void dispatch(const PushTaskRequest *pushTaskRequest) = 0;
    virtual void set_dataset_owner(std::map<std::string, std::string> &dataset_owner) {}
    inline std::string get_node_id() const {
      return node_id_;
    }
    inline std::string platform() {
      return primihub::typeToName(platform_type_);
    }
    inline std::string task_id() {
      return task_id_;
    }
    inline std::string job_id() {
      return job_id_;
    }
    inline void set_scheduler_info(primihub::PlatFormType platform_type,
        const std::string& job_id, const std::string& task_id) {
      platform_type_ = platform_type;
      job_id_ = job_id;
      task_id_ = task_id;
    }

  protected:
    std::string node_id_;
    bool singleton_;
    std::string task_id_;
    std::string job_id_;
    primihub::PlatFormType platform_type_;
};
} // namespace primihub::task

#endif  // SRC_PRIMIHUB_TASK_SEMANTIC_SCHEDULER_H_
