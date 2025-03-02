import json
from pathlib import Path
import os
import re
import time
from nonebot.rule import is_type, to_me, Rule
from nonebot.plugin import on_command, on_message, on_type
from nonebot.adapters.onebot.v11 import MessageSegment, MessageEvent, Message
from nonebot import logger
from datetime import datetime, timedelta
from typing import Tuple, Optional

class time_grouper:
    def __init__(self):
        self.last_time: Optional[datetime] = None
        self.current_day: Optional[datetime.date] = None
        self.current_group_end: Optional[datetime] = None

    def process(self, timestamp_str: str, data_id: int) -> Tuple[Optional[str], Optional[int]]:
        """
        处理数据并返回分组状态
        :param timestamp_str: 时间字符串，格式为'%Y-%m-%d %H:%M:%S'
        :param data_id: 当前数据点的ID
        :return: (新天标识，新组标识)
        """
        new_time = datetime.strptime(timestamp_str, '%Y-%m-%d %H-%M-%S')
        
        # 时间顺序校验
        if self.last_time and new_time <= self.last_time:
            raise ValueError(f"时间非递增，当前时间：{new_time}，上条时间：{self.last_time}")
        self.last_time = new_time

        # 第一条数据处理
        if not self.current_day:
            self.current_day = new_time.date()
            self.current_group_end = new_time
            return (str(self.current_day), data_id)

        # 分组逻辑
        time_diff = new_time - self.current_group_end
        if time_diff > timedelta(minutes=10):
            # 触发新分组
            new_day = new_time.date()
            is_new_day = new_day != self.current_day
            new_day_str = str(new_day) if is_new_day else self.current_day
            
            self.current_day = new_time.date()
            self.current_group_end = new_time
            return (new_day_str, data_id)
        else:
            # 合并到当前组
            self.current_group_end = new_time  # 更新组结束时间
            return (None, None)

spliter = on_message()
grouper = time_grouper()
global current_day
global current_group

@spliter.handle()
async def handle_function(event: MessageEvent):
    if event.message_type == 'group':
        await group_message(event)
    elif event.message_type == 'private':
        await private_message(event)

async def __message(id,event: MessageEvent):
    group_id = id
    dir = Path(f'./saves/{group_id}')
    if not dir.exists():
        dir.mkdir(parents=True)
    
    t = time.strftime("%Y-%m-%d %H-%M-%S", time.localtime())
    file_name = dir / f'{t}.json'

    # 创建时间戳文件
    with open(file_name, 'w') as f:
        f.write(json.dumps(event, default=lambda o: o.__dict__, sort_keys=True, indent=4))

    message_id = event.message_id
    message_type = event.message[0].type
    print(f'[{group_id}] {message_id} {message_type} saved to {file_name}')

    if message_type not in ['image', 'video', 'audio', 'file', 'forward']:
        return

    day_flag, group_flag =  grouper.process(t, message_id)
    
    global current_day
    global current_group

    if day_flag or group_flag or not current_day or not current_group:
        current_day = day_flag
        current_group = group_flag
        print(f'[{group_id}] {message_id} new group: {current_day}/{current_group}')


    out_dir = Path(f'./outs/{current_day}/{current_group}')
    if not out_dir.exists():
        out_dir.mkdir(parents=True)
    out_json_file =  out_dir / f'{message_id}.json'
    with open(out_json_file, 'w') as f:
        f.write(json.dumps(event, default=lambda o: o.__dict__, sort_keys=True, indent=4))
    print(f'[{group_id}] {message_id} saved to {out_json_file}')

    if message_type == 'forward':
        await process_forward(event.message, event.message[0].data['id'])
    elif message_type == 'image':
        await process_image(event.message)
    elif message_type == 'video':
        await process_video(event.message)
    else:
        print(f'[{group_id}] {message_id} saved to {out_json_file}')

async def group_message(event: MessageEvent):
    return await __message(event.group_id,event)
async def private_message(event: MessageEvent):
    return await __message(event.user_id,event)

async def process_forward(message: Message, group_id: int | None):
    print(f'process_forward {message}')
    global current_day

    if message is list and message[0] is dict and 'id' in message[0].data:
        group_id = message[0].data['id']
        out_dir = Path(f'./outs/{current_day}/{group_id}')
        if not out_dir.exists():
            out_dir.mkdir(parents=True)
        out_json_file =  out_dir / f'{group_id}.json'
        with open(out_json_file, 'w') as f:
            f.write(json.dumps(message, default=lambda o: o.__dict__, sort_keys=True, indent=4))
        print(f'{group_id} saved to {out_json_file}')

    # message 的类型？
    print(f'message type: {type(message)}')
    msgs = message
    if type(message) is dict :
        if 'message' in message:
            msgs = message['message']
        print(f'forward su2b {message['message']}')

    for msg in msgs:
        print(f'forward sub {msg}')
        if type(msg) is not dict:
            msg_type = msg.type
            if msg_type not in ['image', 'video', 'audio', 'file', 'forward']:
                continue
            if msg_type == 'forward':
                print(f'forward: {msg.data}')
                id = msg.data['id']
                for m in msg.data['content']:
                    await process_forward(m, id)
            elif msg_type == 'image':
                #image_url = msg.data['url']
                #print(f'{group_id} image: {image_url}')
                #await process_image(msg.data['message'])
                image_url = msg.data['url']
                file_name = Path(f'./outs/{current_day}/{group_id}/{ msg.data['file']}')
                print(f'image {file_name}: {image_url}')
                await download_file(image_url, file_name)
            elif msg_type == 'video':
                video_url = msg.data['url']
                print(f'{group_id} video: {video_url}')
                await process_video(msg.data['message'])
        else:
            msg_type = msg['type']
            if msg_type not in ['image', 'video', 'audio', 'file', 'forward']:
                continue
            if msg_type == 'forward':
                print(f'forward: {msg['data']}')
                id = msg['data']['id']
                for m in msg['data']['content']:
                    await process_forward(m, id)
            elif msg_type == 'image':
                image_url = msg['data']['url']
                file_name = Path(f'./outs/{current_day}/{group_id}/{msg['data']['file']}')
                print(f'image {file_name}: {image_url}')
                await download_file(image_url, file_name)
            elif msg_type == 'video':
                video_url = msg['data']['url']
                file_name = Path(f'./outs/{current_day}/{group_id}/{msg['data']['file']}')
                print(f'video {file_name}: {video_url}')
                await download_file(video_url, file_name)

async def process_image(message: Message):
    print('process_image')
    global current_day
    global current_group

    for msg in message:
        msg_type = msg.type
        if msg_type not in ['image', 'video', 'audio', 'file', 'forward']:
            continue
        if msg_type == 'forward':
            process_forward(msg.data['message'])
        elif msg_type == 'image':
            image_url = msg.data['url']
            file_name = Path(f'./outs/{current_day}/{current_group}/{msg.data['file']}')
            print(f'image {file_name}: {image_url}')
            await download_file(image_url, file_name)

async def process_video(message: Message):
    print('process_video')
    global current_day
    global current_group

    for msg in message:
        msg_type = msg.type
        if msg_type not in ['image', 'video', 'audio', 'file', 'forward']:
            continue
        if msg_type == 'forward':
            process_forward(msg.data['message'])
        elif msg_type == 'video':
            video_url = msg.data['url']
            file_name = Path(f'./outs/{current_day}/{current_group}/{msg.data['file']}')
            print(f'video {file_name}: {video_url}')
            await download_file(video_url, file_name)

from urllib.request import urlopen
import os
import httpx
#import aiofiles
import os
 
async def download_file(url: str, file_name: str) -> None:
    try:
        # 创建目录
        directory = os.path.dirname(file_name)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
 
        # 异步请求
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url)
            response.raise_for_status()
 
        # 异步写入文件
        with open(file_name, 'wb') as f:
            f.write(response.content)
 
    except httpx.HTTPError as e:
        with open('error.log', 'a') as f:
            f.write(f"HTTP错误: {str(e)}, url: {url}, file: {file_name}\n")
        #raise Exception(f"网络错误: {str(e)}")
 